# =============================================================
#  Darmyth — backend/vision/hands.py
#  MediaPipe 0.10.x hand tracking using Tasks API
#  model_complexity=0 equivalent → lite hand landmark model
# =============================================================

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark
import urllib.request
import time
import yaml
import os
from pathlib import Path

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"
MODEL_DIR = BASE_DIR / "data"
MODEL_PATH = MODEL_DIR / "hand_landmarker.task"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

# ── Download model if not present ─────────────────────────────
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

def ensure_model():
    if not MODEL_PATH.exists():
        print("[hands] Downloading hand landmark model (~9MB)...")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[hands] Model downloaded.")
    else:
        print("[hands] Model found.")

# ── Landmark indices ──────────────────────────────────────────
WRIST        = 0
THUMB_TIP    = 4;  THUMB_IP   = 3
INDEX_TIP    = 8;  INDEX_PIP  = 6
MIDDLE_TIP   = 12; MIDDLE_PIP = 10
RING_TIP     = 16; RING_PIP   = 14
PINKY_TIP    = 20; PINKY_PIP  = 18

# ── Drawing helpers ───────────────────────────────────────────
CONNECTIONS = [
    # Thumb
    (0,1),(1,2),(2,3),(3,4),
    # Index
    (0,5),(5,6),(6,7),(7,8),
    # Middle
    (0,9),(9,10),(10,11),(11,12),
    # Ring
    (0,13),(13,14),(14,15),(15,16),
    # Pinky
    (0,17),(17,18),(18,19),(19,20),
    # Palm
    (5,9),(9,13),(13,17),
]

def draw_landmarks(frame, landmarks, w, h):
    """Draw dots and connections on frame."""
    coords = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    # Draw connections
    for a, b in CONNECTIONS:
        cv2.line(frame, coords[a], coords[b], (255, 100, 0), 2)

    # Draw dots
    for i, (x, y) in enumerate(coords):
        color = (0, 255, 180) if i in [4,8,12,16,20] else (255, 255, 255)
        cv2.circle(frame, (x, y), 5, color, -1)

    return coords


# ── Hand tracker class ────────────────────────────────────────
class HandTracker:
    def __init__(self, max_hands: int = 1,
                 detection_confidence: float = 0.7,
                 tracking_confidence: float = 0.5):

        ensure_model()

        base_options = mp_python.BaseOptions(
            model_asset_path=str(MODEL_PATH)
        )
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=max_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=tracking_confidence,
            min_tracking_confidence=tracking_confidence,
            running_mode=mp_vision.RunningMode.VIDEO
        )
        self.detector      = mp_vision.HandLandmarker.create_from_options(options)
        self.landmarks     = None
        self.hand_detected = False
        self._timestamp    = 0

    def process_frame(self, frame):
        """Process frame, detect landmarks, return annotated frame."""
        h, w = frame.shape[:2]
        annotated = frame.copy()

        # Convert to MediaPipe image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # Timestamp must increase each frame
        self._timestamp += 1
        result = self.detector.detect_for_video(mp_image, self._timestamp)

        self.hand_detected = False
        self.landmarks     = None

        if result.hand_landmarks:
            self.hand_detected = True
            self.landmarks     = result.hand_landmarks[0]
            draw_landmarks(annotated, self.landmarks, w, h)

        return annotated

    def get_landmark_coords(self, frame_width: int, frame_height: int) -> list:
        """Return pixel (x, y) for all 21 landmarks."""
        if not self.landmarks:
            return []
        return [
            (int(lm.x * frame_width), int(lm.y * frame_height))
            for lm in self.landmarks
        ]

    def get_finger_states(self) -> dict:
        """Return which fingers are extended (True) or folded (False)."""
        if not self.landmarks:
            return {}
        lm = self.landmarks
        return {
            "index":  lm[INDEX_TIP].y  < lm[INDEX_PIP].y,
            "middle": lm[MIDDLE_TIP].y < lm[MIDDLE_PIP].y,
            "ring":   lm[RING_TIP].y   < lm[RING_PIP].y,
            "pinky":  lm[PINKY_TIP].y  < lm[PINKY_PIP].y,
            "thumb":  lm[THUMB_TIP].x  < lm[THUMB_IP].x,
        }

    def close(self):
        self.detector.close()


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    from backend.vision.camera import Camera

    print("Testing Darmyth hand tracking (MediaPipe 0.10.x)\n")
    print("Controls: Q — quit | F — toggle finger states\n")
    print("Show your hand to the camera!\n")

    cam     = Camera()
    tracker = HandTracker()

    if not cam.start():
        print("Camera failed to start.")
        exit(1)

    show_fingers = True
    frame_count  = 0
    fps_timer    = time.time()
    current_fps  = 0

    while True:
        frame = cam.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w = frame.shape[:2]
        annotated = tracker.process_frame(frame)

        # FPS counter
        frame_count += 1
        if time.time() - fps_timer >= 1.0:
            current_fps = frame_count
            frame_count = 0
            fps_timer   = time.time()

        cv2.putText(annotated, f"FPS: {current_fps}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Hand status
        status = "Hand Detected" if tracker.hand_detected else "No Hand"
        col    = (0, 255, 0) if tracker.hand_detected else (0, 0, 255)
        cv2.putText(annotated, status,
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

        # Finger states
        if show_fingers and tracker.hand_detected:
            fingers = tracker.get_finger_states()
            y = 100
            for finger, extended in fingers.items():
                state = "UP" if extended else "down"
                color = (0, 255, 180) if extended else (100, 100, 100)
                cv2.putText(annotated, f"{finger}: {state}",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
                y += 25

        # Landmark count
        if tracker.hand_detected:
            coords = tracker.get_landmark_coords(w, h)
            cv2.putText(annotated, f"Landmarks: {len(coords)}",
                       (10, h - 40), cv2.FONT_HERSHEY_SIMPLEX,
                       0.55, (200, 200, 200), 1)

        cv2.putText(annotated, "DARMYTH — Hand Tracking",
                   (w - 240, h - 15), cv2.FONT_HERSHEY_SIMPLEX,
                   0.5, (100, 100, 255), 1)

        cv2.imshow("Darmyth — Hand Tracking", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('f'):
            show_fingers = not show_fingers

    tracker.close()
    cam.stop()
    cv2.destroyAllWindows()
    print("[hands] Stopped.")