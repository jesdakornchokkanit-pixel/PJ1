import cv2
import numpy as np
import threading
import time
import os
from insightface.app import FaceAnalysis
from ultralytics import YOLO
from inference_sdk import InferenceHTTPClient
from config import (
    WIDTH, HEIGHT,
    PERSON_MODEL_PATH, PERSON_CONF, FACE_THRESH,
    PERSON_EVERY, FACE_EVERY, MASK_EVERY,
    BLACKLIST_DIR, RF_API_KEY, MASK_MODEL,
    CAMERA_LIST,
)

# ── โหลด Models ───────────────────────────────────────────────────
print("[+] Loading YOLO :", PERSON_MODEL_PATH)
person_model = YOLO(PERSON_MODEL_PATH)

print("[+] Loading InsightFace ...")
face_app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
face_app.prepare(ctx_id=0, det_size=(320, 320), det_thresh=0.3)

rf_client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=RF_API_KEY
)

# ── โหลด Blacklist ────────────────────────────────────────────────
blacklist = {}
for fname in os.listdir(BLACKLIST_DIR):
    if fname.lower().endswith((".jpg", ".jpeg", ".png")):
        img = cv2.imread(os.path.join(BLACKLIST_DIR, fname))
        faces = face_app.get(img)
        if faces:
            base = os.path.splitext(fname)[0]
            name = base.rsplit("_", 1)[0] if base[-1].isdigit() else base
            if name not in blacklist:
                blacklist[name] = []
            blacklist[name].append(faces[0].normed_embedding)
            print(f"  [+] Blacklist: {name} ({fname})")
print(f"[+] Blacklist: {len(blacklist)} person(s)")

# ── Shared state — แยกต่อกล้อง ───────────────────────────────────
num_cams = len(CAMERA_LIST)

detection_results = {
    cam["id"]: {
        "persons":   [],
        "blacklist": [],
        "masks":     [],
    }
    for cam in CAMERA_LIST
}

results_lock  = threading.Lock()
alerts        = []          # [(text, color, expire), ...] รวมทุกกล้อง
latest_frames = {cam["id"]: [None] for cam in CAMERA_LIST}
frame_locks   = {cam["id"]: threading.Lock() for cam in CAMERA_LIST}


def add_alert(text, color=(0, 0, 255)):
    with results_lock:
        now = time.time()
        for a in alerts:
            if a[0] == text and a[2] - now > 2:
                return
        alerts.append([text, color, now + 5])


def detection_worker():
    """
    รัน detection วนไปทีละกล้อง เพื่อแชร์ CPU
    """
    frame_counts = {cam["id"]: 0 for cam in CAMERA_LIST}
    bl_caches    = {cam["id"]: [] for cam in CAMERA_LIST}

    while True:
        for cam in CAMERA_LIST:
            cid = cam["id"]

            with frame_locks[cid]:
                frame = latest_frames[cid][0]
            if frame is None:
                continue

            frame_counts[cid] += 1
            fc = frame_counts[cid]

            if fc % PERSON_EVERY != 0:
                continue

            small  = cv2.resize(frame, (640, 360))
            sx, sy = WIDTH / 640, HEIGHT / 360

            # ── Person ────────────────────────────────────────────
            persons = []
            for r in person_model(frame, classes=[0], verbose=False, conf=PERSON_CONF):
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    if (x2-x1) > WIDTH*0.85 or (y2-y1) > HEIGHT*0.85:
                        continue
                    persons.append((x1, y1, x2, y2, conf))

            # ── Blacklist ─────────────────────────────────────────
            if fc % FACE_EVERY == 0 and blacklist:
                new_hits = []
                try:
                    faces = face_app.get(small)
                    for face in faces:
                        emb = face.normed_embedding
                        for name, emb_list in blacklist.items():
                            scores = [np.dot(emb, e) for e in emb_list]
                            if max(scores) > FACE_THRESH:
                                bb = face.bbox.astype(int)
                                x1 = int(bb[0]*sx); y1 = int(bb[1]*sy)
                                x2 = int(bb[2]*sx); y2 = int(bb[3]*sy)
                                new_hits.append((x1, y1, x2, y2, name))
                                add_alert(f"! [{cam['name']}] Blacklist: {name}", (0,0,255))
                except Exception:
                    pass
                now = time.time()
                bl_caches[cid] = [(x1,y1,x2,y2,n,now+3.0) for x1,y1,x2,y2,n in new_hits]

            # ── Mask ──────────────────────────────────────────────
            masks = []
            if fc % MASK_EVERY == 0:
                try:
                    small_rf = cv2.resize(frame, (416, 234))
                    sx_rf = WIDTH / 416; sy_rf = HEIGHT / 234
                    res = rf_client.infer(small_rf, model_id=MASK_MODEL)
                    for pred in res.get("predictions", []):
                        x1 = int((pred["x"]-pred["width"] /2)*sx_rf)
                        y1 = int((pred["y"]-pred["height"]/2)*sy_rf)
                        x2 = int((pred["x"]+pred["width"] /2)*sx_rf)
                        y2 = int((pred["y"]+pred["height"]/2)*sy_rf)
                        masks.append((x1,y1,x2,y2,pred["class"],pred["confidence"]))
                        add_alert(f"! [{cam['name']}] Face Covered", (0,100,255))
                except Exception:
                    pass

            # ── Update ────────────────────────────────────────────
            with results_lock:
                detection_results[cid]["persons"]   = persons
                detection_results[cid]["blacklist"] = bl_caches[cid]
                if fc % MASK_EVERY == 0:
                    detection_results[cid]["masks"] = masks

        time.sleep(0.01)
