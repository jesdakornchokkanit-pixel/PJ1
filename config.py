import numpy as np

# ══════════════════════════════════════════════════════════════════
#  CAMERAS
# ══════════════════════════════════════════════════════════════════
CAMERA_LIST = [
    {"id": 0, "name": "Cam 01", "url": "rtsp://admin:test2547@192.168.1.65:554/Streaming/Channels/102"},
    {"id": 1, "name": "Cam 02", "url": "rtsp://admin:test2547@192.168.1.64:554/Streaming/Channels/102"},
]

WIDTH, HEIGHT = 1280, 720   # ความละเอียดต่อกล้อง
FFMPEG_PATH   = (
    r"C:\Users\jetsadakorn.ch\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
)

# ══════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════
PERSON_MODEL_PATH = "yolo11n.pt"
PERSON_CONF       = 0.45
FACE_THRESH       = 0.45
PERSON_EVERY      = 2      # รัน YOLO ทุก N frame ต่อกล้อง
FACE_EVERY        = 10     # รัน face ทุก N frame ต่อกล้อง
MASK_EVERY        = 6

# ══════════════════════════════════════════════════════════════════
#  ROBOFLOW
# ══════════════════════════════════════════════════════════════════
RF_API_KEY  = "dE7BkUvwm3nYAL2cVpew"
MASK_MODEL  = "cover-no-aug-v9p0q/1"

# ══════════════════════════════════════════════════════════════════
#  PATHS
# ══════════════════════════════════════════════════════════════════
BLACKLIST_DIR      = r"C:\Users\jetsadakorn.ch\Documents\Test\blacklist"
SNAPSHOT_DIR       = r"C:\Users\jetsadakorn.ch\Documents\Test\snapshots"
AUTO_SNAP_COOLDOWN = 20

# ══════════════════════════════════════════════════════════════════
#  LINE
# ══════════════════════════════════════════════════════════════════
LINE_TOKEN    = "D2UxiNK0wMjihsplDqrMc8l0vMJVrEDo2W10qkVsYFbbY1U7lUpnWzG8zNiBH+bSYZmLV3HHA20ZeNblLrFgRp6qLVFXYzrO7bE6AVthQecAzNs/HQbH0FWrP1/t+d2AroCD0nvRuWyktOTefTpbMAdB04t89/1O/w1cDnyilFU="
LINE_USER_ID  = "U6a678f26632cb7ca440bce01dce80ae3"
LINE_COOLDOWN = 30
IMGBB_API_KEY = "your_imgbb_api_key_here"

# ══════════════════════════════════════════════════════════════════
#  FORBIDDEN ZONES  (แยกต่อกล้อง — key = camera id)
# ══════════════════════════════════════════════════════════════════
FORBIDDEN_ZONES = {
    0: [  # Cam 01
        {
            "name"  : "Door Zone",
            "points": np.array([[850,300],[1080,300],[1080,810],[850,810]], np.int32),
            "color" : (0, 0, 255),
        },
    ],
    1: [],  # Cam 02 — ยังไม่กำหนด zone
}
