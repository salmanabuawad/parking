"""
Tight plate crop extraction.
Never run OCR on whole frame; only on tight plate crops with small configurable margin.
Clips safely to frame boundaries.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def crop_plate(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    margin_px: int = 4,
) -> np.ndarray | None:
    """
    Extract a tight crop of the plate region from the frame.
    bbox: (x, y, w, h) in frame coordinates.
    margin_px: small margin around the plate (configurable).
    Returns crop clipped to frame bounds, or None if invalid.
    """
    x, y, w, h = bbox
    h_frame, w_frame = frame.shape[:2]
    pad = max(0, margin_px)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w_frame, x + w + pad)
    y2 = min(h_frame, y + h + pad)
    if x1 >= x2 or y1 >= y2:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size < 100:
        return None
    return crop


def crop_plate_xyxy(
    frame: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    margin_px: int = 4,
) -> np.ndarray | None:
    """Extract plate crop from (x1,y1,x2,y2) bbox. Clips to frame."""
    w, h = x2 - x1, y2 - y1
    return crop_plate(frame, (x1, y1, w, h), margin_px)
