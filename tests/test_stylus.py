# =============================================================
#  Darmyth — tests/test_stylus.py
#  Air stylus — cursor + click + drag + glowing ring cursor
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
from backend.automation.cursor_style import CursorManager

if __name__ == "__main__":
    print("Darmyth Air Stylus")
    print("☝  Index up          → move cursor")
    print("🤌 Quick pinch       → left click")
    print("🤌 Hold pinch + move → drag / select")
    print("Move mouse to TOP-LEFT corner to emergency stop")
    print("Q to quit\n")

    cam           = Camera()
    tracker       = HandTracker()
    classifier    = GestureClassifier(
        pinch_threshold=0.28,
        click_cooldown=0.5,
        drag_delay=0.3,
        entry_grace=0.4,
        stable_needed=3
    )
    cursor        = CursorController(smoothing=0.85,
                                     active_zone=(0.2, 0.15, 0.8, 0.85))
    cursor_style  = CursorManager()

    # Apply glowing ring cursor on start
    cursor_style.apply_glowing_ring(size=32, color=(0, 220, 255))

    if not cam.start():
        print("Camera failed.")
        cursor_style.restore()
        exit(1)

    frame_count = 0
    fps_timer   = time.time()
    current_fps = 0
    click_flash = 0

    try:
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

            action    = "none"
            triggered = False
            gesture   = Gesture.UNKNOWN

            if tracker.hand_detected:
                gesture, action, triggered = classifier.get_action(
                    tracker.landmarks, tracker.hand_detected
                )
                cursor.process(gesture, action, triggered, tracker.landmarks)

                if action == "click":
                    click_flash = time.time()

                # Draw index fingertip
                if tracker.landmarks:
                    lm = tracker.landmarks
                    ix = int(lm[8].x * w)
                    iy = int(lm[8].y * h)

                    if cursor.is_dragging:
                        dot_color  = (0, 100, 255)
                        ring_color = (0, 100, 255)
                    elif time.time() - click_flash < 0.2:
                        dot_color  = (0, 255, 0)
                        ring_color = (0, 255, 0)
                    else:
                        dot_color  = (0, 255, 180)
                        ring_color = (255, 255, 255)

                    cv2.circle(annotated, (ix, iy), 16, ring_color, 2)
                    cv2.circle(annotated, (ix, iy), 10, dot_color, -1)
                    cv2.line(annotated,(ix-22,iy),(ix-13,iy),ring_color,1)
                    cv2.line(annotated,(ix+13,iy),(ix+22,iy),ring_color,1)
                    cv2.line(annotated,(ix,iy-22),(ix,iy-13),ring_color,1)
                    cv2.line(annotated,(ix,iy+13),(ix,iy+22),ring_color,1)

            # Active zone
            x0=int(w*0.2); y0=int(h*0.15)
            x1=int(w*0.8); y1=int(h*0.85)
            cv2.rectangle(annotated,(x0,y0),(x1,y1),(60,60,60),1)
            cv2.putText(annotated,"active zone",(x0+4,y0+16),
                       cv2.FONT_HERSHEY_SIMPLEX,0.4,(60,60,60),1)

            # Status bar
            cv2.rectangle(annotated,(0,h-55),(w,h),(15,15,15),-1)
            now = time.time()

            if cursor.is_dragging:
                cv2.putText(annotated,"DRAGGING",
                           (10,h-12),cv2.FONT_HERSHEY_SIMPLEX,1.0,(0,100,255),2)
            elif now - click_flash < 0.3:
                cv2.putText(annotated,"CLICK!",
                           (10,h-12),cv2.FONT_HERSHEY_SIMPLEX,1.1,(0,255,0),2)
            elif tracker.hand_detected:
                label = "PINCHING — hold to drag" if classifier._was_pinching else "POINTING"
                color = (0,200,255) if classifier._was_pinching else (0,255,180)
                cv2.putText(annotated,label,
                           (10,h-12),cv2.FONT_HERSHEY_SIMPLEX,0.85,color,2)
            else:
                cv2.putText(annotated,"No hand",
                           (10,h-12),cv2.FONT_HERSHEY_SIMPLEX,0.8,(80,80,80),1)

            cv2.putText(annotated,f"FPS:{current_fps}",
                       (w-100,25),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,0),1)

            cv2.imshow("Darmyth — Air Stylus", annotated)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Always restore cursor and release mouse on exit
        if cursor.is_dragging:
            import pyautogui
            pyautogui.mouseUp()
        cursor_style.restore()
        tracker.close()
        cam.stop()
        cv2.destroyAllWindows()
        print("Stopped — cursor restored.")
