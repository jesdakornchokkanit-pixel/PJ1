import cv2
import numpy as np
import threading
import time
import os
import math
import requests
import base64

from config import (
    WIDTH, HEIGHT, CAMERA_LIST,
    SNAPSHOT_DIR, AUTO_SNAP_COOLDOWN,
    LINE_TOKEN, LINE_USER_ID, LINE_COOLDOWN,
    IMGBB_API_KEY, FORBIDDEN_ZONES,
)
from camera import FFmpegCamera
from detection import (
    detection_worker, detection_results, results_lock,
    alerts, latest_frames, frame_locks, add_alert,
)

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def iou_overlap(b1, b2):
    return (max(b1[0],b2[0]) < min(b1[2],b2[2]) and
            max(b1[1],b2[1]) < min(b1[3],b2[3]))

def point_in_polygon(px, py, polygon):
    return cv2.pointPolygonTest(polygon, (float(px), float(py)), False) >= 0

def person_in_zone(x1, y1, x2, y2, zone_pts):
    return point_in_polygon((x1+x2)//2, y2, zone_pts)

def draw_text_outline(f, text, pos, scale, color, thickness=2):
    cv2.putText(f, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                scale, (0,0,0), thickness+4, cv2.LINE_AA)
    cv2.putText(f, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)

def draw_corner_box(f, x1, y1, x2, y2, color, thickness=3, L=30):
    corners = [
        ((x1,y1),(x1+L,y1)), ((x1,y1),(x1,y1+L)),
        ((x2,y1),(x2-L,y1)), ((x2,y1),(x2,y1+L)),
        ((x1,y2),(x1+L,y2)), ((x1,y2),(x1,y2-L)),
        ((x2,y2),(x2-L,y2)), ((x2,y2),(x2,y2-L)),
    ]
    for p1, p2 in corners:
        cv2.line(f, p1, p2, color, thickness, cv2.LINE_AA)
    ov = f.copy()
    cv2.rectangle(ov, (x1,y1), (x2,y2), color, 1)
    cv2.addWeighted(ov, 0.20, f, 0.80, 0, f)

# ── Snapshot ──────────────────────────────────────────────────────
last_snap_time = {}
def auto_snapshot(frame, reason):
    now = time.time()
    if now - last_snap_time.get(reason, 0) < AUTO_SNAP_COOLDOWN:
        return None
    last_snap_time[reason] = now
    fname = os.path.join(SNAPSHOT_DIR,
                         f"{time.strftime('%Y%m%d_%H%M%S')}_{reason}.jpg")
    cv2.imwrite(fname, frame)
    return fname

# ── Line + imgbb ──────────────────────────────────────────────────
last_line_time = {}
def upload_imgbb(image_path):
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    try:
        res = requests.post("https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY, "image": data}, timeout=10)
        return res.json()["data"]["url"]
    except Exception:
        return None

def send_line(message, image_path=None):
    now = time.time()
    key = message[:20]
    if now - last_line_time.get(key, 0) < LINE_COOLDOWN:
        return
    last_line_time[key] = now
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    msgs    = [{"type": "text", "text": message}]
    if image_path:
        url = upload_imgbb(image_path)
        if url:
            msgs.append({"type":"image",
                         "originalContentUrl": url,
                         "previewImageUrl"   : url})
    try:
        requests.post("https://api.line.me/v2/bot/message/push",
            headers=headers,
            json={"to": LINE_USER_ID, "messages": msgs},
            timeout=10)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
#  DRAW SINGLE CAMERA FRAME
# ══════════════════════════════════════════════════════════════════
def render_camera(frame, cid, cam_name, active_alerts):
    with results_lock:
        persons   = list(detection_results[cid]["persons"])
        bl_hits   = list(detection_results[cid]["blacklist"])
        masks     = list(detection_results[cid]["masks"])

    bl_hits = [b for b in bl_hits if b[5] > time.time()]
    zones   = FORBIDDEN_ZONES.get(cid, [])

    # ── Forbidden Zones ───────────────────────────────────────────
    for zone in zones:
        ov = frame.copy()
        cv2.fillPoly(ov, [zone["points"]], zone["color"])
        cv2.addWeighted(ov, 0.15, frame, 0.85, 0, frame)
        cv2.polylines(frame, [zone["points"]], True, zone["color"], 2, cv2.LINE_AA)
        pts = zone["points"]
        draw_text_outline(frame, f"! {zone['name']}",
                          (int(pts[:,0].mean())-40, int(pts[:,1].min())-10),
                          0.5, zone["color"])

    # ── Zone intrusion ────────────────────────────────────────────
    intruder_idx = set()
    for i, (x1,y1,x2,y2,_) in enumerate(persons):
        for zone in zones:
            if person_in_zone(x1,y1,x2,y2,zone["points"]):
                intruder_idx.add(i)
                add_alert(f"! [{cam_name}] Intrusion: {zone['name']}", (0,0,255))

    # ── Masks ─────────────────────────────────────────────────────
    for x1,y1,x2,y2,cls,conf in masks:
        draw_corner_box(frame, x1,y1,x2,y2, (0,100,255), thickness=3)
        draw_text_outline(frame, f"! Cover {conf:.0%}",
                          (x1, max(y1-8,15)), 0.55, (0,100,255))

    # ── Persons ───────────────────────────────────────────────────
    for i, (x1,y1,x2,y2,conf) in enumerate(persons):
        is_bl = any(iou_overlap((x1,y1,x2,y2),(bx1,by1,bx2,by2))
                    for bx1,by1,bx2,by2,_,_ in bl_hits)
        if is_bl:
            continue
        if i in intruder_idx:
            color, label, thick = (0,0,255), f"! INTRUDER {conf:.0%}", 3
        else:
            color, label, thick = (0,255,0), f"Person {conf:.0%}", 2
        draw_corner_box(frame, x1,y1,x2,y2, color, thickness=thick, L=20)
        draw_text_outline(frame, label, (x1, max(y1-8,15)), 0.55, color)

    # ── Blacklist ─────────────────────────────────────────────────
    for x1,y1,x2,y2,name,_ in bl_hits:
        draw_corner_box(frame, x1,y1,x2,y2, (0,0,255), thickness=3, L=20)
        draw_text_outline(frame, f"! BL:{name}",
                          (x1, max(y1-8,15)), 0.55, (0,0,255))

    # ── Status bar ────────────────────────────────────────────────
    ov = frame.copy()
    cv2.rectangle(ov, (0,0), (WIDTH, 40), (0,0,0), -1)
    cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
    draw_text_outline(frame, cam_name,           (8, 28), 0.65, (255,255,255))
    draw_text_outline(frame, f"P:{len(persons)}",(160,28), 0.65,
                      (0,255,0) if persons else (120,120,120))
    draw_text_outline(frame, f"BL:{len(bl_hits)}",(240,28), 0.65,
                      (0,0,255) if bl_hits else (120,120,120))

    # ── Auto snapshot + Line ──────────────────────────────────────
    if bl_hits:
        path = auto_snapshot(frame, f"cam{cid}_blacklist")
        send_line(f"🚨 [{cam_name}] Blacklist: {bl_hits[0][4]}", path)
    for text, color, _ in active_alerts:
        if text.startswith("!") and f"[{cam_name}]" in text:
            path = auto_snapshot(frame, text.replace(" ","_").replace(":","")[:40])
            send_line(f"⚠️ {text}", path)

    return frame

# ══════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════
cameras = {}
for cam in CAMERA_LIST:
    c = FFmpegCamera(cam["id"], cam["url"], cam["name"]).start()
    cameras[cam["id"]] = c

threading.Thread(target=detection_worker, daemon=True).start()

print("[*] Waiting for cameras...")
time.sleep(3)

# ── Grid layout ───────────────────────────────────────────────────
n_cams  = len(CAMERA_LIST)
n_cols  = math.ceil(math.sqrt(n_cams))
n_rows  = math.ceil(n_cams / n_cols)
CELL_W  = 960  // n_cols
CELL_H  = 540  // n_rows
GRID_W  = CELL_W * n_cols
GRID_H  = CELL_H * n_rows

cv2.namedWindow("Security Monitor", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Security Monitor", GRID_W, GRID_H)

# ══════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════
while True:
    grid = np.zeros((GRID_H, GRID_W, 3), np.uint8)

    with results_lock:
        now           = time.time()
        active_alerts = [a for a in alerts if a[2] > now]
        alerts[:]     = active_alerts

    for idx, cam in enumerate(CAMERA_LIST):
        cid   = cam["id"]
        frame = cameras[cid].read()

        row = idx // n_cols
        col = idx  % n_cols
        x0  = col * CELL_W
        y0  = row * CELL_H

        if frame is None:
            cell = np.zeros((CELL_H, CELL_W, 3), np.uint8)
            draw_text_outline(cell, "Connecting...",
                              (10, CELL_H//2), 0.6, (0,255,255))
        else:
            # อัพเดท latest_frame สำหรับ detection
            with frame_locks[cid]:
                latest_frames[cid][0] = frame.copy()

            cell = cv2.resize(frame, (CELL_W, CELL_H))
            # scale factor สำหรับ bounding box
            sx = CELL_W / WIDTH
            sy = CELL_H / HEIGHT

            # scale detection results ให้เข้า cell
            with results_lock:
                persons_raw   = list(detection_results[cid]["persons"])
                bl_hits_raw   = list(detection_results[cid]["blacklist"])
                masks_raw     = list(detection_results[cid]["masks"])

            # scale persons
            detection_results[cid]["persons"] = [
                (int(x1*sx),int(y1*sy),int(x2*sx),int(y2*sy),c)
                for x1,y1,x2,y2,c in persons_raw]
            detection_results[cid]["blacklist"] = [
                (int(x1*sx),int(y1*sy),int(x2*sx),int(y2*sy),n,e)
                for x1,y1,x2,y2,n,e in bl_hits_raw]
            detection_results[cid]["masks"] = [
                (int(x1*sx),int(y1*sy),int(x2*sx),int(y2*sy),cl,cf)
                for x1,y1,x2,y2,cl,cf in masks_raw]

            # scale zones
            scaled_zones = FORBIDDEN_ZONES.get(cid, [])
            orig_zones   = FORBIDDEN_ZONES.get(cid, [])
            FORBIDDEN_ZONES[cid] = [
                {**z, "points": (z["points"] * np.array([sx,sy])).astype(np.int32)}
                for z in orig_zones
            ]

            cell = render_camera(cell, cid, cam["name"], active_alerts)

            # restore
            FORBIDDEN_ZONES[cid]              = orig_zones
            detection_results[cid]["persons"]  = persons_raw
            detection_results[cid]["blacklist"]= bl_hits_raw
            detection_results[cid]["masks"]    = masks_raw

        grid[y0:y0+CELL_H, x0:x0+CELL_W] = cell

    # ── Timestamp + Alerts ────────────────────────────────────────
    ts = time.strftime("%Y-%m-%d  %H:%M:%S")
    draw_text_outline(grid, ts, (GRID_W-320, 28), 0.7, (255,255,255))

    for i, (text, color, _) in enumerate(active_alerts[:5]):
        draw_text_outline(grid, text, (8, 70+i*35), 0.65, color)

    cv2.imshow("Security Monitor", grid)

    key = cv2.waitKey(1) & 0xFF
    if key in [ord("q"), 27]:
        break
    elif key == ord("s"):
        fname = os.path.join(SNAPSHOT_DIR, f"grid_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
        cv2.imwrite(fname, grid)
        add_alert("Snapshot saved", (0,255,180))

for cam in cameras.values():
    cam.stop()
cv2.destroyAllWindows()
