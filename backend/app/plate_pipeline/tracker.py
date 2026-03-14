"""Plate tracker: temporal smoothing and reuse on missing frames."""

from __future__ import annotations

from typing import Optional, Tuple

from .config import TRACK_IOU_MIN, TRACK_MAX_MISSES, TRACK_SMOOTHING_ALPHA, TRACK_STABLE_AFTER

BBox = Tuple[int, int, int, int]


class PlateTracker:
    """Track plate box across frames with smoothing, IOU gating, and stability count."""

    def __init__(
        self,
        max_misses: int = TRACK_MAX_MISSES,
        alpha: float = TRACK_SMOOTHING_ALPHA,
        iou_min: float = TRACK_IOU_MIN,
        stable_after: int = TRACK_STABLE_AFTER,
    ):
        self.max_misses = max_misses
        self.alpha = alpha
        self.iou_min = iou_min
        self.stable_after = stable_after
        self.last_box: Optional[BBox] = None
        self.miss_count = 0
        self.stable_hits = 0

    def update(self, box: Optional[BBox]) -> Optional[BBox]:
        if box is not None:
            self.miss_count = 0
            if self.last_box is None:
                self.last_box = box
                self.stable_hits = 1
                return box

            if _iou_xywh(self.last_box, box) < self.iou_min:
                self.last_box = box
                self.stable_hits = 1
                return box

            x = int(self.alpha * box[0] + (1 - self.alpha) * self.last_box[0])
            y = int(self.alpha * box[1] + (1 - self.alpha) * self.last_box[1])
            w = int(self.alpha * box[2] + (1 - self.alpha) * self.last_box[2])
            h = int(self.alpha * box[3] + (1 - self.alpha) * self.last_box[3])
            self.last_box = (x, y, w, h)
            self.stable_hits += 1
            return self.last_box

        self.miss_count += 1
        if self.miss_count > self.max_misses:
            self.last_box = None
            self.stable_hits = 0
            return None
        return self.last_box

    @property
    def is_stable(self) -> bool:
        return self.last_box is not None and self.stable_hits >= self.stable_after

    def reset(self) -> None:
        self.last_box = None
        self.miss_count = 0
        self.stable_hits = 0


def _iou_xywh(a: BBox, b: BBox) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0
