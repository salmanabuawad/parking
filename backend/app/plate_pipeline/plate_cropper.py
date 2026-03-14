"""Tight plate crop extraction and crop quality checks."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def crop_plate(
    frame: np.ndarray,
    bbox: Tuple[int, int, int, int],
    margin_px: int = 4,
) -> np.ndarray | None:
    """Extract a tight crop of the plate region from the frame."""
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
    """Extract plate crop from (x1,y1,x2,y2) bbox."""
    w, h = x2 - x1, y2 - y1
    return crop_plate(frame, (x1, y1, w, h), margin_px)


def estimate_crop_quality(crop: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    return {
        "width": float(gray.shape[1]),
        "height": float(gray.shape[0]),
        "sharpness": sharpness,
        "brightness": brightness,
    }


def is_crop_ocr_ready(
    crop: np.ndarray,
    min_width: int,
    min_height: int,
    min_sharpness: float,
    min_brightness: float,
    max_brightness: float,
) -> bool:
    q = estimate_crop_quality(crop)
    return (
        q["width"] >= min_width
        and q["height"] >= min_height
        and q["sharpness"] >= min_sharpness
        and min_brightness <= q["brightness"] <= max_brightness
    )
