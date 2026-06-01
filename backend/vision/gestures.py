# =============================================================
#  Darmyth — backend/vision/gestures.py
#  Minimal air stylus — index tip cursor + pinch left click
#  No freeze, no right click, no scroll yet
# =============================================================

import time
import math


class Gesture:
    POINT      = "point"       # index up — move cursor
    PINCH_LEFT = "pinch_left"  # thumb+index close — left click
    UNKNOWN    = "unknown"


class GestureClassifier:
    def __init__(self,
                 pinch_threshold: float = 0.28,
                 click_cooldown: float  = 0.5,
                 entry_grace: float     = 0.4,
                 stable_needed: int     = 3):

        self.pinch_threshold = pinch_threshold
        self.click_cooldown  = click_cooldown
        self.entry_grace     = entry_grace
        self.stable_needed   = stable_needed

        self._last_click_time   = 0
        self._hand_entered_time = 0
        self._hand_was_present  = False
        self._stable_gesture    = Gesture.UNKNOWN
        self._stable_count      = 0

    def _dist(self, a, b) -> float:
        return math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2)

    def _norm_dist(self, lm, a, b) -> float:
        hand_size = self._dist(lm[0], lm[5])
        if hand_size < 0.001:
            return 999
        return self._dist(lm[a], lm[b]) / hand_size

    def classify(self, landmarks, hand_present: bool) -> str:
        if not hand_present or landmarks is None:
            self._hand_was_present = False
            return Gesture.UNKNOWN

        # Entry grace
        if not self._hand_was_present:
            self._hand_entered_time = time.time()
            self._hand_was_present  = True

        lm = landmarks

        # Pinch check — thumb tip (4) close to index tip (8)
        ti_dist = self._norm_dist(lm, 4, 8)
        if ti_dist < self.pinch_threshold:
            return Gesture.PINCH_LEFT

        # Everything else = pointing/cursor
        return Gesture.POINT

    def get_action(self, landmarks, hand_present: bool) -> tuple:
        """Returns (gesture, triggered)."""
        gesture = self.classify(landmarks, hand_present)

        # Stability
        if gesture == self._stable_gesture:
            self._stable_count += 1
        else:
            self._stable_gesture = gesture
            self._stable_count   = 0

        stable = self._stable_count >= self.stable_needed

        # Cursor — always trigger when hand present, no cooldown
        if gesture == Gesture.POINT:
            return gesture, hand_present

        # Click — cooldown
        now = time.time()
        if gesture == Gesture.PINCH_LEFT and stable:
            if now - self._last_click_time >= self.click_cooldown:
                self._last_click_time = now
                return gesture, True

        return gesture, False
