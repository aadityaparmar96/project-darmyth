# =============================================================
#  Darmyth — backend/voice/wake_word.py
#  Wake word detection using openWakeWord
#  Listens passively in background thread
#  Fires callback when "hey jarvis" or custom word detected
#  Note: openWakeWord doesn't have "hey darmyth" built in
#  We use "hey jarvis" as closest available + rename in UI
# =============================================================

# =============================================================
#  Darmyth — backend/voice/wake_word.py
#  Dual activation: "Hey Jarvis" wake word + Ctrl+Shift+D hotkey
#  Both trigger the same on_detected callback
# =============================================================

# =============================================================
#  Darmyth — backend/voice/wake_word.py
#  Dual activation: "Hey Jarvis" wake word + Ctrl+Shift+D hotkey
#  Stereo mic input converted to mono for openWakeWord
# =============================================================

# =============================================================
#  Darmyth — backend/voice/wake_word.py
#  Dual activation: "Hey Jarvis" wake word + Ctrl+Shift+D hotkey
#  channels=1 mono — works on all Realtek devices
# =============================================================

import threading
import numpy as np
import sounddevice as sd
import time

WAKE_WORD_MODEL = "hey_jarvis"
THRESHOLD       = 0.5
MIC_DEVICE      = 2    # Microphone Array (Realtek) — mono


class WakeWordDetector:
    CHUNK_SIZE  = 1280
    SAMPLE_RATE = 16000

    def __init__(self, on_detected=None, threshold: float = THRESHOLD):
        self.on_detected    = on_detected or (lambda: print("[wake] Activated!"))
        self.threshold      = threshold
        self._running       = False
        self._wake_thread   = None
        self._hotkey_thread = None
        self._model         = None
        self._cooldown      = 2.0
        self._last_trigger  = 0

    def _trigger(self, source: str):
        now = time.time()
        if now - self._last_trigger >= self._cooldown:
            self._last_trigger = now
            print(f"[wake] Activated via {source}!")
            if self.on_detected:
                self.on_detected()

    # ── Wake word ─────────────────────────────────────────────
    def _load_model(self):
        try:
            from openwakeword.model import Model
            self._model = Model(
                wakeword_models=[WAKE_WORD_MODEL],
                inference_framework="onnx"
            )
            print(f"[wake] Wake word model loaded: {WAKE_WORD_MODEL}")
        except Exception as e:
            print(f"[wake] Wake word model failed: {e}")
            self._model = None

    def _wake_word_loop(self):
        self._load_model()
        if self._model is None:
            print("[wake] Wake word disabled — hotkey only.")
            return

        print("[wake] Say 'Hey Jarvis' OR press Ctrl+Shift+D to activate")

        def audio_callback(indata, frames, time_info, status):
            if not self._running:
                return
            audio       = indata[:, 0].astype(np.float32)
            audio_int16 = (audio * 32767).astype(np.int16)
            prediction  = self._model.predict(audio_int16)
            score = prediction.get(WAKE_WORD_MODEL, 0)
            if isinstance(score, (list, np.ndarray)):
                score = float(score[-1])
            if score >= self.threshold:
                self._trigger("hey_jarvis")

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocksize=self.CHUNK_SIZE,
                callback=audio_callback,
                device=MIC_DEVICE
            ):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            print(f"[wake] Audio stream error: {e}")
            print("[wake] Falling back to hotkey only.")

    # ── Hotkey ────────────────────────────────────────────────
    def _hotkey_loop(self):
        try:
            import keyboard
            print("[wake] Hotkey ready: Ctrl+Shift+D")
            keyboard.add_hotkey(
                'ctrl+shift+d',
                lambda: self._trigger("Ctrl+Shift+D")
            )
            while self._running:
                time.sleep(0.1)
            keyboard.remove_hotkey('ctrl+shift+d')
        except ImportError:
            print("[wake] Run: pip install keyboard")
        except Exception as e:
            print(f"[wake] Hotkey error: {e}")

    # ── Start / Stop ──────────────────────────────────────────
    def start(self):
        self._running = True

        self._wake_thread = threading.Thread(
            target=self._wake_word_loop, daemon=True
        )
        self._wake_thread.start()

        self._hotkey_thread = threading.Thread(
            target=self._hotkey_loop, daemon=True
        )
        self._hotkey_thread.start()

        print("[wake] Detector started.")

    def stop(self):
        self._running = False
        if self._wake_thread:
            self._wake_thread.join(timeout=2)
        if self._hotkey_thread:
            self._hotkey_thread.join(timeout=2)
        print("[wake] Detector stopped.")


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    detected_count = [0]

    def on_wake():
        detected_count[0] += 1
        print(f"\n*** DARMYTH ACTIVATED #{detected_count[0]} ***\n")

    print("Darmyth Wake Word Test")
    print("Trigger 1: Say 'Hey Jarvis'")
    print("Trigger 2: Press Ctrl+Shift+D")
    print("Running for 60 seconds... Ctrl+C to stop\n")

    detector = WakeWordDetector(on_detected=on_wake, threshold=0.5)
    detector.start()

    try:
        time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        detector.stop()
        print(f"\nTotal activations: {detected_count[0]}")