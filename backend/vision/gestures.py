# =============================================================
#  Darmyth — backend/vision/gestures.py
#  Air stylus — cursor + click + drag
# =============================================================

import time
import math


class Gesture:
    POINT      = "point"        # index up — move cursor
    PINCH_LEFT = "pinch_left"   # thumb+index — click / drag
    UNKNOWN    = "unknown"


class GestureClassifier:
    def __init__(self,
                 pinch_threshold: float = 0.28,
                 click_cooldown: float  = 0.5,
                 drag_delay: float      = 0.3,
                 entry_grace: float     = 0.4,
                 stable_needed: int     = 3):
        """
        drag_delay: seconds pinch must be held before becoming a drag
                    under this = click, over this = drag
        """
        self.pinch_threshold = pinch_threshold
        self.click_cooldown  = click_cooldown
        self.drag_delay      = drag_delay
        self.entry_grace     = entry_grace
        self.stable_needed   = stable_needed

        self._last_click_time   = 0
        self._hand_entered_time = 0
        self._hand_was_present  = False
        self._stable_gesture    = Gesture.UNKNOWN
        self._stable_count      = 0

        # Drag state
        self._pinch_start_time  = None   # when pinch began
        self._is_dragging       = False  # currently in drag mode
        self._was_pinching      = False  # pinch was active last frame

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

        if not self._hand_was_present:
            self._hand_entered_time = time.time()
            self._hand_was_present  = True

        lm      = landmarks
        ti_dist = self._norm_dist(lm, 4, 8)

        if ti_dist < self.pinch_threshold:
            return Gesture.PINCH_LEFT

        return Gesture.POINT

    def get_action(self, landmarks, hand_present: bool) -> tuple:
        """
        Returns (gesture, action, triggered) where action is one of:
            'move'        — move cursor
            'click'       — single left click
            'drag_start'  — mouseDown, begin drag
            'drag_move'   — dragging, cursor follows
            'drag_end'    — mouseUp, drag released
        """
        gesture = self.classify(landmarks, hand_present)

        # Stability
        if gesture == self._stable_gesture:
            self._stable_count += 1
        else:
            self._stable_gesture = gesture
            self._stable_count   = 0

        stable = self._stable_count >= self.stable_needed
        now    = time.time()

        # ── Hand left frame — end any active drag ─────────────
        if not hand_present:
            if self._is_dragging:
                self._is_dragging      = False
                self._pinch_start_time = None
                self._was_pinching     = False
                return Gesture.POINT, "drag_end", True
            return Gesture.UNKNOWN, "none", False

        # ── Cursor movement — always on when pointing ─────────
        if gesture == Gesture.POINT:
            # If we were pinching and release — check if it was a click
            if self._was_pinching:
                if self._is_dragging:
                    # End drag
                    self._is_dragging      = False
                    self._pinch_start_time = None
                    self._was_pinching     = False
                    return gesture, "drag_end", True
                else:
                    # Was a click (short pinch)
                    self._pinch_start_time = None
                    self._was_pinching     = False
                    if now - self._last_click_time >= self.click_cooldown:
                        self._last_click_time = now
                        return gesture, "click", True
            self._was_pinching = False
            return gesture, "move", True

        # ── Pinch ─────────────────────────────────────────────
        if gesture == Gesture.PINCH_LEFT and stable:
            # First frame of pinch
            if not self._was_pinching:
                self._pinch_start_time = now
                self._was_pinching     = True
                return gesture, "move", False   # wait to decide click vs drag

            pinch_duration = now - (self._pinch_start_time or now)

            if self._is_dragging:
                # Already dragging — keep dragging
                return gesture, "drag_move", True

            elif pinch_duration >= self.drag_delay:
                # Held long enough — start drag
                self._is_dragging = True
                return gesture, "drag_start", True

            else:
                # Still deciding — move cursor but don't click yet
                return gesture, "move", True

        return gesture, "none", False

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging
