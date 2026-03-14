"""
Blur pipeline: blur entire frame, restore only validated target plate.
If no validated plate, keep whole frame blurred.
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import BLUR_KERNEL_SIZE


def blur_frame(frame: np.ndarray, kernel_size: int = BLUR_KERNEL_SIZE) -> np.ndarray:
    """Blur entire frame."""
    k = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
    return cv2.boxFilter(frame, -1, (k, k))


def restore_plate_region(
    blurred: np.ndarray,
    sharp_crop: np.ndarray,
    bbox: tuple[int, int, int, int],
) -> np.ndarray:
    """
    Paste sharp plate crop back onto blurred frame at bbox.
    bbox: (x, y, w, h)
    """
    x, y, w, h = bbox
    h_f, w_f = blurred.shape[:2]
    # Resize crop if needed to match bbox
    if sharp_crop.shape[1] != w or sharp_crop.shape[0] != h:
        sharp_crop = cv2.resize(sharp_crop, (w, h), interpolation=cv2.INTER_CUBIC)
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w_f, x + w), min(h_f, y + h)
    sh, sw = sharp_crop.shape[:2]
    # Clip crop to what fits
    cx1 = x1 - x
    cy1 = y1 - y
    cx2 = cx1 + (x2 - x1)
    cy2 = cy1 + (y2 - y1)
    if cx1 < 0 or cy1 < 0 or cx2 > sw or cy2 > sh:
        return blurred
    roi = sharp_crop[cy1:cy2, cx1:cx2]
    out = blurred.copy()
    out[y1:y2, x1:x2] = roi
    return out


def blur_except_plate(
    frame: np.ndarray,
    plate_bbox: tuple[int, int, int, int] | None,
    kernel_size: int = BLUR_KERNEL_SIZE,
) -> np.ndarray:
    """
    Blur frame, then restore plate region if provided.
    If plate_bbox is None, return fully blurred frame.
    """
    blurred = blur_frame(frame, kernel_size)
    if plate_bbox is None:
        return blurred
    x, y, w, h = plate_bbox
    sharp = frame[y : y + h, x : x + w].copy()
    return restore_plate_region(blurred, sharp, plate_bbox)
