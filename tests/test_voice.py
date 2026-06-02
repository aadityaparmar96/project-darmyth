# =============================================================
#  Darmyth — tests/test_voice.py
#  Full voice pipeline test:
#  Wake word → STT → brain.py → TTS
# =============================================================

import sys
import os
import time
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.voice.wake_word import WakeWordDetector
from backend.voice.stt import STT
from backend.voice.tts import TTS
from backend.assistant.brain import chat, clear_history

# ── State ─────────────────────────────────────────────────────
is_listening  = False   # True when actively recording after wake word
tts           = TTS()
stt           = STT()


def handle_wake_word():
    """Called when wake word detected — start listening."""
    global is_listening
    if is_listening:
        return   # already listening

    is_listening = True
    print("\n[pipeline] Wake word detected — listening...")
    tts.speak("Yes?", block=False)
    time.sleep(0.8)   # wait for TTS to finish

    # Record and transcribe
    text = stt.listen(duration=5.0)

    if not text:
        print("[pipeline] Nothing heard.")
        tts.speak("I didn't catch that.", block=False)
        is_listening = False
        return

    print(f"\nYou said: '{text}'")

    # Send to brain
    print("[pipeline] Thinking...")
    response = chat(text)

    print(f"Darmyth: {response}")
    tts.speak(response, block=True)

    is_listening = False


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Darmyth Voice Pipeline Test")
    print("=" * 50)
    print("Say 'Hey Jarvis' to activate Darmyth")
    print("Then speak your command or question")
    print("Ctrl+C to stop\n")

    # Greet on start
    tts.speak("Darmyth voice pipeline active. Say hey Jarvis to begin.", block=True)

    detector = WakeWordDetector(
        on_detected=handle_wake_word,
        threshold=0.5
    )
    detector.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[pipeline] Shutting down...")
    finally:
        detector.stop()
        tts.speak("Goodbye.", block=True)
        print("[pipeline] Done.")