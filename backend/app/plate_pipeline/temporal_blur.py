"""Temporal blur tracking.

Keeps a blur/restoration box alive for a few missed frames and predicts a small
forward motion using the last two reliable boxes. This reduces one-frame leaks
when the detector drops a plate briefly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

BBox = Tuple[int, int, int, int]  # x, y, w, h


@dataclass
class TemporalBlurState:
    box: Optional[BBox]
    miss_count: int
    velocity: tuple[float, float]


class TemporalBlurTracker:
    def __init__(self, max_misses: int = 6, expand_ratio: float = 0.18):
        self.max_misses = max_misses
        self.expand_ratio = max(0.0, float(expand_ratio))
        self._last_box: Optional[BBox] = None
        self._prev_box: Optional[BBox] = None
        self._miss_count = 0

    def update(self, detected_box: Optional[BBox]) -> Optional[BBox]:
        if detected_box is not None:
            self._prev_box = self._last_box
            self._last_box = self._expand(detected_box)
            self._miss_count = 0
            return self._last_box

        if self._last_box is None:
            return None

        self._miss_count += 1
        if self._miss_count > self.max_misses:
            self.reset()
            return None

        predicted = self._predict_next_box()
        self._prev_box = self._last_box
        self._last_box = predicted
        return predicted

    def reset(self) -> None:
        self._last_box = None
        self._prev_box = None
        self._miss_count = 0

    def snapshot(self) -> TemporalBlurState:
        vx, vy = self._velocity()
        return TemporalBlurState(box=self._last_box, miss_count=self._miss_count, velocity=(vx, vy))

    def _velocity(self) -> tuple[float, float]:
        if self._prev_box is None or self._last_box is None:
            return (0.0, 0.0)
        return (
            float(self._last_box[0] - self._prev_box[0]),
            float(self._last_box[1] - self._prev_box[1]),
        )

    def _predict_next_box(self) -> BBox:
        assert self._last_box is not None
        vx, vy = self._velocity()
        x, y, w, h = self._last_box
        decay = max(0.25, 1.0 - (self._miss_count * 0.18))
        return (
            int(round(x + vx * decay)),
            int(round(y + vy * decay)),
            w,
            h,
        )

    def _expand(self, box: BBox) -> BBox:
        x, y, w, h = box
        pad_x = int(round(w * self.expand_ratio))
        pad_y = int(round(h * self.expand_ratio))
        return (x - pad_x, y - pad_y, w + (2 * pad_x), h + (2 * pad_y))
