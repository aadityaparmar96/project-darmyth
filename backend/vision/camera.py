# =============================================================
#  Darmyth — backend/vision/camera.py
#  Webcam capture module — Windows 11 optimised
#  Runs in its own thread, feeds frames to hands.py
#  Resolution: 480p, FPS cap: 15 (saves CPU on i5)
# =============================================================

import cv2
import threading
import time
import yaml
from pathlib import Path

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

WIDTH   = SETTINGS["vision"]["resolution"][0]   # 640
HEIGHT  = SETTINGS["vision"]["resolution"][1]   # 480
FPS_CAP = SETTINGS["vision"]["fps_cap"]         # 15


# ── Camera class ──────────────────────────────────────────────
class Camera:
    """
    Manages webcam capture in a background thread.
    Other modules (hands.py, overlay.py) call get_frame()
    to get the latest frame without blocking.
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap          = None
        self.frame        = None
        self.running      = False
        self._thread      = None
        self._lock        = threading.Lock()
        self._frame_time  = 1.0 / FPS_CAP  # seconds between frames

    def start(self) -> bool:
        """
        Open the webcam and start the capture thread.
        Returns True if successful, False if camera not found.
        """
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        # CAP_DSHOW = DirectShow backend — faster on Windows 11

        if not self.cap.isOpened():
            print(f"[camera] ERROR: Could not open camera {self.camera_index}")
            print("[camera] Try changing camera_index to 1 if you have multiple cameras")
            return False

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, FPS_CAP)

        # Confirm actual resolution (camera may not support exact values)
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[camera] Started — resolution: {actual_w}x{actual_h} @ {FPS_CAP}fps cap")

        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def _capture_loop(self):
        """Background thread — continuously reads frames from webcam."""
        while self.running:
            start = time.time()

            ret, frame = self.cap.read()
            if ret:
                # Flip horizontally — mirror effect (feels natural)
                frame = cv2.flip(frame, 1)
                with self._lock:
                    self.frame = frame
            else:
                print("[camera] WARNING: Failed to read frame")

            # FPS cap — sleep to avoid eating CPU
            elapsed = time.time() - start
            sleep_time = self._frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def get_frame(self):
        """
        Get the latest frame (thread-safe).
        Returns None if no frame is available yet.
        """
        with self._lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        """Stop the capture thread and release the webcam."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.cap:
            self.cap.release()
        print("[camera] Stopped.")


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth camera...\n")
    print("Controls:")
    print("  Q — quit")
    print("  S — save screenshot")
    print("  F — toggle FPS display\n")

    cam = Camera()

    if not cam.start():
        print("Could not start camera. Check if webcam is connected.")
        exit(1)

    show_fps   = True
    frame_count = 0
    fps_timer   = time.time()
    current_fps = 0

    while True:
        frame = cam.get_frame()

        if frame is None:
            time.sleep(0.01)
            continue

        # FPS counter
        frame_count += 1
        if time.time() - fps_timer >= 1.0:
            current_fps = frame_count
            frame_count = 0
            fps_timer   = time.time()

        # Draw UI overlay on frame
        display = frame.copy()

        if show_fps:
            cv2.putText(display, f"FPS: {current_fps}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, (0, 255, 0), 2)

        # Darmyth watermark
        cv2.putText(display, "DARMYTH",
                   (WIDTH - 110, HEIGHT - 15),
                   cv2.FONT_HERSHEY_SIMPLEX,
                   0.5, (100, 100, 255), 1)

        # Status
        cv2.putText(display, "Camera Active",
                   (10, HEIGHT - 15),
                   cv2.FONT_HERSHEY_SIMPLEX,
                   0.5, (0, 255, 0), 1)

        cv2.imshow("Darmyth — Camera Feed", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("[camera] Quit.")
            break
        elif key == ord('s'):
            filename = f"screenshot_{int(time.time())}.png"
            cv2.imwrite(filename, frame)
            print(f"[camera] Screenshot saved: {filename}")
        elif key == ord('f'):
            show_fps = not show_fps

    cam.stop()
    cv2.destroyAllWindows()