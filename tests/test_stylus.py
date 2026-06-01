# =============================================================
#  Darmyth — tests/test_stylus.py
#  Minimal air stylus test — cursor + click only
# =============================================================

import cv2
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.vision.camera import Camera
from backend.vision.hands import HandTracker
from backend.vision.gestures import GestureClassifier, Gesture
from backend.automation.cursor import CursorController

if __name__ == "__main__":
    print("Darmyth Air Stylus — Minimal Mode")
    print("☝  Index finger  → move cursor")
    print("🤌 Pinch         → left click")
    print("Move mouse to TOP-LEFT corner to emergency stop")
    print("Q to quit\n")

    cam        = Camera()
    tracker    = HandTracker()
    classifier = GestureClassifier(
        pinch_threshold=0.28,
        click_cooldown=0.5,
        entry_grace=0.4,
        stable_needed=3
    )
    cursor = CursorController(
        smoothing=0.9,
        active_zone=(0.2, 0.15, 0.8, 0.85)   # center 60% → full screen
    )

    if not cam.start():
        print("Camera failed.")
        exit(1)

    frame_count  = 0
    fps_timer    = time.time()
    current_fps  = 0
    last_gesture = Gesture.UNKNOWN
    click_flash  = 0   # timestamp of last click for visual flash

    while True:
        frame = cam.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w      = frame.shape[:2]
        annotated = tracker.process_frame(frame)

        # FPS
        frame_count += 1
        if time.time() - fps_timer >= 1.0:
            current_fps = frame_count
            frame_count = 0
            fps_timer   = time.time()

        gesture   = Gesture.UNKNOWN
        triggered = False

        if tracker.hand_detected:
            gesture, triggered = classifier.get_action(
                tracker.landmarks, tracker.hand_detected
            )
            cursor.process(gesture, triggered, tracker.landmarks)
            last_gesture = gesture

            if gesture == Gesture.PINCH_LEFT and triggered:
                click_flash = time.time()

            # Draw index fingertip indicator
            if tracker.landmarks:
                lm = tracker.landmarks
                ix = int(lm[8].x * w)
                iy = int(lm[8].y * h)

                # Outer ring — white
                cv2.circle(annotated, (ix, iy), 16, (255, 255, 255), 2)

                # Inner dot — cyan normally, green on click
                dot_color = (0, 255, 0) if (time.time() - click_flash < 0.2) else (0, 255, 180)
                cv2.circle(annotated, (ix, iy), 10, dot_color, -1)

                # Crosshair lines
                cv2.line(annotated, (ix-20, iy), (ix-12, iy), (255,255,255), 1)
                cv2.line(annotated, (ix+12, iy), (ix+20, iy), (255,255,255), 1)
                cv2.line(annotated, (ix, iy-20), (ix, iy-12), (255,255,255), 1)
                cv2.line(annotated, (ix, iy+12), (ix, iy+20), (255,255,255), 1)

        # Active zone box — shows usable area
        x0 = int(w * 0.2);  y0 = int(h * 0.15)
        x1 = int(w * 0.8);  y1 = int(h * 0.85)
        cv2.rectangle(annotated, (x0, y0), (x1, y1), (60, 60, 60), 1)
        cv2.putText(annotated, "active zone",
                   (x0+4, y0+16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60,60,60), 1)

        # Status bar
        cv2.rectangle(annotated, (0, h-50), (w, h), (15,15,15), -1)

        if time.time() - click_flash < 0.3:
            cv2.putText(annotated, "CLICK!",
                       (10, h-12), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0,255,0), 2)
        elif tracker.hand_detected:
            label = "PINCHING" if gesture == Gesture.PINCH_LEFT else "POINTING"
            color = (0,255,100) if gesture == Gesture.PINCH_LEFT else (0,255,180)
            cv2.putText(annotated, label,
                       (10, h-12), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        else:
            cv2.putText(annotated, "No hand detected",
                       (10, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80,80,80), 1)

        cv2.putText(annotated, f"FPS: {current_fps}",
                   (w-110, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,0), 1)

        cv2.imshow("Darmyth — Air Stylus", annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    tracker.close()
    cam.stop()
    cv2.destroyAllWindows()
    print("Stopped.")
