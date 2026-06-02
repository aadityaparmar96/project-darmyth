# =============================================================
#  Darmyth — backend/voice/stt.py
#  Speech-to-text using faster-whisper (base model)
#  beam_size=5 for better accuracy on i5
# =============================================================

import sounddevice as sd
import numpy as np
import threading
import time
import yaml
from pathlib import Path

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

WHISPER_MODEL = SETTINGS["voice"]["whisper_model"]           # base
UNLOAD_AFTER  = SETTINGS["voice"]["whisper_unload_after_sec"]  # 30

# ── Mic device index ──────────────────────────────────────────
# 3  = Microphone Array (Realtek) — laptop mic
# 2  = Headset (Stone 358) — use this if wearing headset
MIC_DEVICE = 3


class STT:
    """
    Records from mic and transcribes using Whisper base.
    Loads model on first use, unloads after idle to save RAM.
    """

    SAMPLE_RATE = 16000

    def __init__(self, mic_device: int = MIC_DEVICE):
        self.mic_device    = mic_device
        self._model        = None
        self._model_lock   = threading.Lock()
        self._last_used    = 0
        self._unload_timer = None

    def _load_model(self):
        if self._model is None:
            print("[stt] Loading Whisper model...")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                WHISPER_MODEL,
                device="cpu",
                compute_type="int8"
            )
            print(f"[stt] Whisper '{WHISPER_MODEL}' ready.")

    def _schedule_unload(self):
        if self._unload_timer:
            self._unload_timer.cancel()

        def _unload():
            with self._model_lock:
                if self._model and (time.time() - self._last_used) >= UNLOAD_AFTER:
                    self._model = None
                    print("[stt] Whisper unloaded (idle).")

        self._unload_timer = threading.Timer(UNLOAD_AFTER, _unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def record(self, duration: float = 5.0) -> np.ndarray:
        print(f"[stt] Recording {duration}s — speak now!")
        audio = sd.rec(
            int(duration * self.SAMPLE_RATE),
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype='float32',
            device=self.mic_device
        )
        sd.wait()
        print("[stt] Done recording.")
        return audio.flatten()

    def transcribe(self, audio: np.ndarray) -> str:
        with self._model_lock:
            self._load_model()
            self._last_used = time.time()

            segments, info = self._model.transcribe(
                audio,
                beam_size=5,                    # accuracy over speed
                language="en",                  # skip language detection
                vad_filter=True,                # skip silence
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
                temperature=0.0,               # deterministic output
                condition_on_previous_text=False,
            )

            text = " ".join(seg.text.strip() for seg in segments).strip()
            print(f"[stt] Transcribed: '{text}'")
            self._schedule_unload()
            return text

    def listen(self, duration: float = 5.0) -> str:
        """Record then transcribe in one call."""
        audio = self.record(duration)
        return self.transcribe(audio)


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth STT")
    print("Using: Whisper base, beam_size=5")
    print("Mic: Microphone Array (Realtek) — device 3\n")

    stt  = STT()
    text = stt.listen(duration=5.0)

    print(f"\nResult: '{text}'")
    if not text:
        print("Nothing detected — try speaking louder or switch to device=2 (headset)")
    else:
        print("STT working!")