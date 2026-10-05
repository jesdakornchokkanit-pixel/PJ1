import subprocess
import threading
import numpy as np
import time
from config import FFMPEG_PATH, WIDTH, HEIGHT


class FFmpegCamera:
    def __init__(self, cam_id, url, name="Camera"):
        self.cam_id  = cam_id
        self.url     = url
        self.name    = name
        self.frame   = None
        self.running = False
        self.lock    = threading.Lock()
        self.proc    = None

    def _start_proc(self):
        return subprocess.Popen([
            FFMPEG_PATH, "-loglevel", "error",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-rtsp_transport", "tcp", "-timeout", "3000000",
            "-i", self.url,
            "-vf", f"scale={WIDTH}:{HEIGHT}",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"
        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)

    def _reader(self):
        frame_size = WIDTH * HEIGHT * 3
        while self.running:
            try:
                self.proc = self._start_proc()
                print(f"[+] FFmpeg connected: {self.name}")
                while self.running:
                    raw = self.proc.stdout.read(frame_size)
                    if len(raw) != frame_size:
                        break
                    frame = np.frombuffer(raw, np.uint8).reshape((HEIGHT, WIDTH, 3))
                    with self.lock:
                        self.frame = frame
            except Exception as e:
                print(f"[!] {self.name} error: {e}")
            finally:
                if self.proc:
                    self.proc.kill()
            time.sleep(2)

    def start(self):
        self.running = True
        threading.Thread(target=self._reader, daemon=True).start()
        return self

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        if self.proc:
            self.proc.kill()
