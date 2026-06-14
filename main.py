# =============================================================
#  Darmyth — main.py
#  Central orchestrator
#  Stylus is OFF by default — activated/deactivated on command
# =============================================================

import threading
import time
import sys
import os
import cv2

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


# =============================================================
#  Global state
# =============================================================
is_listening   = False
is_running     = True
stylus_active  = False   # stylus is OFF by default
stylus_thread  = None


# =============================================================
#  TTS / STT (always on)
# =============================================================
tts = TTS()
stt = STT()


# =============================================================
#  Stylus — starts and stops on command
# =============================================================
def start_stylus():
    """Start camera + hand tracking in a background thread."""
    global stylus_active, stylus_thread

    if stylus_active:
        tts.speak("Stylus is already active.", block=False)
        return

    stylus_active = True
    tts.speak("Stylus activated.", block=False)
    print("[main] Starting stylus...")

    stylus_thread = threading.Thread(
        target=_stylus_loop, daemon=True
    )
    stylus_thread.start()


def stop_stylus():
    """Stop the stylus cleanly."""
    global stylus_active

    if not stylus_active:
        tts.speak("Stylus is not active.", block=False)
        return

    stylus_active = False
    tts.speak("Stylus closed.", block=False)
    print("[main] Stylus stopped.")


def _stylus_loop():
    """Runs in background thread while stylus is active."""
    global stylus_active, is_running

    # Init components
    cam        = Camera()
    tracker    = HandTracker()
    classifier = GestureClassifier(
        pinch_threshold=0.28,
        click_cooldown=0.5,
        drag_delay=0.3,
        entry_grace=0.4,
        stable_needed=3
    )
    cursor     = CursorController(
        smoothing=0.15,
        active_zone=(0.2, 0.15, 0.8, 0.85)
    )
    cursor_mgr = CursorManager()

    if not cam.start():
        print("[stylus] Camera failed.")
        stylus_active = False
        tts.speak("Camera failed to start.", block=False)
        return

    cursor_mgr.apply_glowing_ring(size=32, color=(0, 220, 255))
    print("[stylus] Active — show your hand.")

    while stylus_active and is_running:
        frame = cam.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w      = frame.shape[:2]
        annotated = tracker.process_frame(frame)

        if tracker.hand_detected:
            gesture, action, triggered = classifier.get_action(
                tracker.landmarks, tracker.hand_detected
            )
            cursor.process(gesture, action, triggered, tracker.landmarks)

            if tracker.landmarks:
                lm = tracker.landmarks
                ix = int(lm[8].x * w)
                iy = int(lm[8].y * h)
                dot_color = (0,100,255) if cursor.is_dragging else (0,255,180)
                cv2.circle(annotated, (ix,iy), 16, (255,255,255), 2)
                cv2.circle(annotated, (ix,iy), 10, dot_color, -1)

        # Status bar
        cv2.rectangle(annotated, (0,h-45),(w,h),(15,15,15),-1)
        if is_listening:
            cv2.putText(annotated, "LISTENING...",
                       (10,h-12), cv2.FONT_HERSHEY_SIMPLEX,
                       0.8, (0,255,100), 2)
        else:
            status = "DRAGGING" if cursor.is_dragging else \
                     ("Hand Active" if tracker.hand_detected else "No Hand")
            col = (0,100,255) if cursor.is_dragging else \
                  ((0,255,180) if tracker.hand_detected else (80,80,80))
            cv2.putText(annotated, status,
                       (10,h-12), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, col, 2)

        cv2.putText(annotated,
                   "DARMYTH Stylus  |  Say 'close stylus' to exit",
                   (10,25), cv2.FONT_HERSHEY_SIMPLEX,
                   0.45, (150,150,255), 1)

        cv2.imshow("Darmyth — Stylus", annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            stylus_active = False
            break

    # Cleanup
    if cursor.is_dragging:
        import pyautogui
        pyautogui.mouseUp()
    cursor_mgr.restore()
    tracker.close()
    cam.stop()
    cv2.destroyAllWindows()
    print("[stylus] Closed.")


# =============================================================
#  Voice pipeline
# =============================================================
def handle_activation():
    """Hotkey/wake word fires this — spawns thread."""
    thread = threading.Thread(target=_do_activation, daemon=True)
    thread.start()


def _do_activation():
    global is_listening

    if is_listening:
        return

    is_listening = True
    print("\n[main] Listening...")
    tts.speak("Yes?", block=False)
    time.sleep(0.8)

    text = stt.listen(duration=6.0)

    if not text:
        tts.speak("I didn't catch that.", block=False)
        is_listening = False
        return

    print(f"\nYou: {text}")
    response = _process(text)
    print(f"Darmyth: {response}\n")
    tts.speak(response, block=False)
    is_listening = False


def _process(text: str) -> str:
    """Route text to the right handler."""
    result = route(text)

    if result["handled"]:
        response = result["response"]

        # Handle special signals
        if response == "CLEAR_MEMORY":
            clear_history()
            return "Memory cleared."
        if response == "STYLUS_ON":
            threading.Thread(target=start_stylus, daemon=True).start()
            return "Starting stylus."
        if response == "STYLUS_OFF":
            stop_stylus()
            return "Stylus closed."

        return response

    # Send to Groq
    print("[main] Thinking...")
    return chat(text)


# =============================================================
#  Main
# =============================================================
def main():
    global is_running

    print("=" * 55)
    print("  DARMYTH — AI Desktop Assistant")
    print("=" * 55)
    print("  Ctrl+Shift+D or 'Hey Jarvis' → activate voice")
    print("  Say 'activate stylus'         → start hand control")
    print("  Say 'close stylus'            → stop hand control")
    print("  Say 'goodbye Darmyth'         → shut down")
    print("  Ctrl+C                        → force quit")
    print("=" * 55 + "\n")

    # ── Index vault ───────────────────────────────────────────
    print("[main] Indexing Obsidian vault...")
    index_vault()
    print()

    # ── Wake word + hotkey ────────────────────────────────────
    print("[main] Starting wake word detector...")
    detector = WakeWordDetector(
        on_detected=handle_activation,
        threshold=0.5
    )
    detector.start()

    # ── Greet ─────────────────────────────────────────────────
    tts.speak(
        "Darmyth is online. Press Control Shift D to speak, "
        "or say hey Jarvis.",
        block=False
    )

    # ── Keep alive ────────────────────────────────────────────
    try:
        while is_running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[main] Shutting down...")
        is_running = False

    # ── Cleanup ───────────────────────────────────────────────
    stop_stylus()
    detector.stop()
    tts.speak("Goodbye.", block=True)
    print("[main] Done.")


if __name__ == "__main__":
    main()