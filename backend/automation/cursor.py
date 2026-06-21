# =============================================================
#  Darmyth — backend/automation/cursor.py
#  Cursor controller — move, click, drag
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
        self.smoothing   = smoothing
        self.active_zone = active_zone
        self._cur_x      = SCREEN_W // 2
        self._cur_y      = SCREEN_H // 2
        self._is_dragging = False

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

    def process(self, gesture: str, action: str,
                triggered: bool, landmarks) -> str:
        """
        Returns action string for UI display.
        """
        if landmarks is None or not triggered:
            return action

        tip = landmarks[8]   # index fingertip
        tx, ty = self._map(tip.x, tip.y)
        self._smooth(tx, ty)

        if action == "move":
            pyautogui.moveTo(self._cur_x, self._cur_y)

        elif action == "click":
            pyautogui.click(self._cur_x, self._cur_y)
            print(f"[cursor] Click → ({self._cur_x}, {self._cur_y})")

        elif action == "drag_start":
            pyautogui.mouseDown(self._cur_x, self._cur_y)
            self._is_dragging = True
            print(f"[cursor] Drag start → ({self._cur_x}, {self._cur_y})")

        elif action == "drag_move":
            pyautogui.moveTo(self._cur_x, self._cur_y)

        elif action == "drag_end":
            pyautogui.mouseUp()
            self._is_dragging = False
            print(f"[cursor] Drag end → ({self._cur_x}, {self._cur_y})")

        return action

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging
