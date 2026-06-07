# =============================================================
#  Darmyth — main.py
#  Central orchestrator — ties all modules together
#  Threads: vision, voice, brain all run concurrently
#
#  Controls:
#    Ctrl+Shift+D  — activate voice input
#    Q (in camera window) — quit
#    Ctrl+C        — quit from terminal
# =============================================================

import threading
import time
import sys
import os

# ── Vision ────────────────────────────────────────────────────
from backend.vision.camera   import Camera
from backend.vision.hands    import HandTracker
from backend.vision.gestures import GestureClassifier, Gesture

# ── Automation ────────────────────────────────────────────────
from backend.automation.cursor       import CursorController
from backend.automation.cursor_style import CursorManager

# ── Voice ─────────────────────────────────────────────────────
from backend.voice.wake_word import WakeWordDetector
from backend.voice.stt       import STT
from backend.voice.tts       import TTS

# ── Assistant ─────────────────────────────────────────────────
from backend.assistant.brain  import chat, clear_history
from backend.assistant.router import route

# ── RAG ───────────────────────────────────────────────────────
from backend.rag.retriever import index_vault

# ── OpenCV (for camera window) ────────────────────────────────
import cv2


# =============================================================
#  Global state
# =============================================================
is_listening  = False   # True when actively recording voice
is_running    = True    # False = shutdown everything


# =============================================================
#  Voice pipeline
# =============================================================
tts = TTS()
stt = STT()

def handle_activation():
    """Called when wake word or hotkey fires — runs in new thread."""
    thread = threading.Thread(target=_do_activation, daemon=True)
    thread.start()

def _do_activation():
    global is_listening

    if is_listening:
        return

    is_listening = True
    print("\n[main] Activated — listening...")
    tts.speak("Yes?", block=False)
    time.sleep(0.8)

    text = stt.listen(duration=5.0)

    if not text:
        print("[main] Nothing heard.")
        tts.speak("I didn't catch that.", block=False)
        is_listening = False
        return

    print(f"\nYou: {text}")

    result = route(text)
    if result["handled"]:
        response = result["response"]
        if response == "CLEAR_MEMORY":
            clear_history()
            response = "Memory cleared."
    else:
        print("[main] Thinking...")
        response = chat(text)

    print(f"Darmyth: {response}\n")
    tts.speak(response, block=False)
    is_listening = False


# =============================================================
#  Vision pipeline
# =============================================================
def vision_loop(cam, tracker, classifier, cursor):
    """Runs in its own thread — handles webcam + gestures."""
    global is_running

    print("[main] Vision thread started.")

    while is_running:
        frame = cam.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w      = frame.shape[:2]
        annotated = tracker.process_frame(frame)

        if tracker.hand_detected:
            fingers  = tracker.get_finger_states()
            gesture, action, triggered = classifier.get_action(
                tracker.landmarks, tracker.hand_detected
            )
            cursor.process(gesture, action, triggered, tracker.landmarks)

            # Draw index fingertip
            if tracker.landmarks:
                lm = tracker.landmarks
                ix = int(lm[8].x * w)
                iy = int(lm[8].y * h)

                dot_color  = (0, 100, 255) if cursor.is_dragging else (0, 255, 180)
                ring_color = (255, 255, 255)
                cv2.circle(annotated, (ix, iy), 16, ring_color, 2)
                cv2.circle(annotated, (ix, iy), 10, dot_color, -1)

        # Status overlay
        cv2.rectangle(annotated, (0, h-45), (w, h), (15,15,15), -1)

        if is_listening:
            cv2.putText(annotated, "LISTENING...",
                       (10, h-12), cv2.FONT_HERSHEY_SIMPLEX,
                       0.8, (0, 255, 100), 2)
        else:
            status = "DRAGGING" if cursor.is_dragging else ("Hand Active" if tracker.hand_detected else "No Hand")
            col    = (0,100,255) if cursor.is_dragging else ((0,255,180) if tracker.hand_detected else (80,80,80))
            cv2.putText(annotated, status,
                       (10, h-12), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, col, 2)

        cv2.putText(annotated, "DARMYTH  |  Q to quit  |  Ctrl+Shift+D to speak",
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                   0.45, (150, 150, 255), 1)

        cv2.imshow("Darmyth", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[main] Q pressed — shutting down.")
            is_running = False
            break

    print("[main] Vision thread stopped.")


# =============================================================
#  Main
# =============================================================
def main():
    global is_running

    print("=" * 55)
    print("  DARMYTH — AI Desktop Assistant")
    print("=" * 55)
    print("  Ctrl+Shift+D or say 'Hey Jarvis' → activate voice")
    print("  Q (camera window) → quit")
    print("  Move mouse to top-left corner → emergency stop")
    print("=" * 55 + "\n")

    # ── Index Obsidian vault ──────────────────────────────────
    print("[main] Indexing Obsidian vault...")
    index_vault()
    print()

    # ── Init vision ───────────────────────────────────────────
    print("[main] Starting vision...")
    cam        = Camera()
    tracker    = HandTracker()
    classifier = GestureClassifier(
        pinch_threshold=0.28,
        click_cooldown=0.5,
        drag_delay=0.3,
        entry_grace=0.4,
        stable_needed=3
    )
    cursor = CursorController(
        smoothing=0.15,
        active_zone=(0.2, 0.15, 0.8, 0.85)
    )

    if not cam.start():
        print("[main] Camera failed — running without vision.")
        cam = None

    # ── Apply glowing cursor ──────────────────────────────────
    cursor_mgr = CursorManager()
    cursor_mgr.apply_glowing_ring(size=32, color=(0, 220, 255))

    # ── Init wake word detector ───────────────────────────────
    print("[main] Starting wake word detector...")
    detector = WakeWordDetector(
        on_detected=handle_activation,
        threshold=0.5
    )
    detector.start()

    # ── Start vision in background thread ─────────────────────
    if cam:
        vision_thread = threading.Thread(
            target=vision_loop,
            args=(cam, tracker, classifier, cursor),
            daemon=True
        )
        vision_thread.start()

    # ── Greet ─────────────────────────────────────────────────
    tts.speak("Darmyth is online. Press Control Shift D to speak.", block=False)

    # ── Main loop — keep alive until vision quits ─────────────
    try:
        while is_running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[main] Ctrl+C — shutting down.")
        is_running = False

    # ── Cleanup ───────────────────────────────────────────────
    print("[main] Shutting down...")

    detector.stop()

    if cam:
        if cursor.is_dragging:
            import pyautogui
            pyautogui.mouseUp()
        tracker.close()
        cam.stop()

    cursor_mgr.restore()
    cv2.destroyAllWindows()

    tts.speak("Goodbye.", block=True)
    print("[main] Done.")


if __name__ == "__main__":
    main()