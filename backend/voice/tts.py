# =============================================================
#  Darmyth — backend/voice/tts.py
#  Text-to-speech using edge-tts + pygame playback
#  Works with Bluetooth headphones on Windows
# =============================================================

import asyncio
import edge_tts
import tempfile
import os
import threading
import yaml
from pathlib import Path

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

VOICE = SETTINGS["voice"]["tts_voice"]   # en-US-GuyNeural


# ── TTS engine ────────────────────────────────────────────────
class TTS:
    def __init__(self, voice: str = None):
        self.voice     = voice or VOICE
        self._lock     = threading.Lock()
        self._speaking = False

    def _play_audio(self, filepath: str):
        """Play mp3 using pygame — works with Bluetooth."""
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                import time
                time.sleep(0.1)
            pygame.mixer.quit()
        except Exception as e:
            print(f"[tts] Playback error: {e}")
        finally:
            try:
                os.unlink(filepath)
            except Exception:
                pass
            self._speaking = False

    async def _synthesize(self, text: str) -> str:
        """Generate speech and save to temp mp3. Returns filepath."""
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(tmp.name)
        return tmp.name

    def speak(self, text: str, block: bool = False) -> None:
        if not text or not text.strip():
            return

        print(f"[tts] Speaking: {text[:60]}{'...' if len(text)>60 else ''}")

        def _run():
            with self._lock:
                self._speaking = True
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    filepath = loop.run_until_complete(self._synthesize(text))
                    loop.close()
                    self._play_audio(filepath)
                except Exception as e:
                    print(f"[tts] Error: {e}")
                    self._speaking = False

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        if block:
            thread.join()

    def speak_sync(self, text: str) -> None:
        self.speak(text, block=True)

    @property
    def is_speaking(self) -> bool:
        return self._speaking


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    print("Testing Darmyth TTS...\n")
    print("Make sure your headphones are connected and set as default audio device.\n")

    tts = TTS()

    lines = [
        "Good Morning Sir, Darmyth here, your AI desktop assistant.",
        "I can hear you, see your hands, and help you get things done.",
        "Let's get started.",
    ]

    for line in lines:
        print(f"Speaking: {line}")
        tts.speak_sync(line)
        time.sleep(0.3)

    print("\nTTS test complete.")