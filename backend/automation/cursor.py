# =============================================================
#  Darmyth — backend/automation/cursor.py
#  Index fingertip → screen cursor
#  Active zone = center 60% of camera → full screen
#  No freeze, no complex gestures
# =============================================================

import pyautogui
from backend.vision.gestures import Gesture

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0

SCREEN_W, SCREEN_H = pyautogui.size()


class CursorController:
    def __init__(self,
                 smoothing: float   = 0.15,
                 active_zone: tuple = (0.2, 0.15, 0.8, 0.85)):
        """
        smoothing: 0=instant/jittery, 1=very smooth/laggy
        active_zone: (x_min, y_min, x_max, y_max) normalised
                     only this portion of camera maps to full screen
                     smaller zone = less arm movement needed
        """
        self.smoothing   = smoothing
        self.active_zone = active_zone

        self._cur_x = SCREEN_W // 2
        self._cur_y = SCREEN_H // 2

    def _map(self, nx: float, ny: float) -> tuple:
        x0, y0, x1, y1 = self.active_zone
        x = (nx - x0) / (x1 - x0)
        y = (ny - y0) / (y1 - y0)
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        return int(x * SCREEN_W), int(y * SCREEN_H)

    def _smooth(self, tx: int, ty: int):
        s = self.smoothing
        self._cur_x = int(self._cur_x * s + tx * (1 - s))
        self._cur_y = int(self._cur_y * s + ty * (1 - s))

    def process(self, gesture: str, triggered: bool, landmarks) -> None:
        if landmarks is None:
            return

        tip = landmarks[8]   # index fingertip

        if gesture == Gesture.POINT and triggered:
            tx, ty = self._map(tip.x, tip.y)
            self._smooth(tx, ty)
            pyautogui.moveTo(self._cur_x, self._cur_y)

        elif gesture == Gesture.PINCH_LEFT and triggered:
            # Move to pinch position then click
            tx, ty = self._map(tip.x, tip.y)
            self._smooth(tx, ty)
            pyautogui.click(self._cur_x, self._cur_y)
            print(f"[cursor] Click → ({self._cur_x}, {self._cur_y})")
