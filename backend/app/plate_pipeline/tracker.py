"""
Plate tracker: temporal smoothing and reuse on missing frames.
Reuse last good box for limited frames when detector misses.
"""
from __future__ import annotations

from typing import Optional, Tuple

from .config import TRACK_MAX_MISSES, TRACK_SMOOTHING_ALPHA


class PlateTracker:
    """Track plate box across frames with smoothing and miss recovery."""

    def __init__(
        self,
        max_misses: int = TRACK_MAX_MISSES,
        alpha: float = TRACK_SMOOTHING_ALPHA,
    ):
        self.max_misses = max_misses
        self.alpha = alpha
        self.last_box: Optional[Tuple[int, int, int, int]] = None
        self.miss_count = 0

    def update(self, box: Optional[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
        """
        box: (x, y, w, h) from detector, or None if not detected.
        Returns smoothed/tracked box or None.
        """
        if box is not None:
            self.miss_count = 0
            if self.last_box is None:
                self.last_box = box
                return box
            # Smooth: new = alpha*current + (1-alpha)*prev
            x = int(self.alpha * box[0] + (1 - self.alpha) * self.last_box[0])
            y = int(self.alpha * box[1] + (1 - self.alpha) * self.last_box[1])
            w = int(self.alpha * box[2] + (1 - self.alpha) * self.last_box[2])
            h = int(self.alpha * box[3] + (1 - self.alpha) * self.last_box[3])
            self.last_box = (x, y, w, h)
            return self.last_box
        self.miss_count += 1
        if self.miss_count > self.max_misses:
            self.last_box = None
            return None
        return self.last_box

    def reset(self) -> None:
        self.last_box = None
        self.miss_count = 0
