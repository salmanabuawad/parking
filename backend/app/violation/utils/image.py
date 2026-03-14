"""Image utilities for violation pipeline."""
from __future__ import annotations

import cv2
import numpy as np


def gaussian_blur(frame: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    k = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
    return cv2.GaussianBlur(frame, (k, k), 0)


def crop_bbox(frame: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]
    x1 = max(0, min(x1, w - 1))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h - 1))
    y2 = max(0, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return frame[0:0, 0:0]
    return frame[y1:y2, x1:x2]


def paste_bbox(dst: np.ndarray, src: np.ndarray, bbox: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    h, w = src.shape[:2]
    x1 = max(0, min(x1, w - 1))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h - 1))
    y2 = max(0, min(y2, h))
    if x2 > x1 and y2 > y1:
        dst[y1:y2, x1:x2] = src[y1:y2, x1:x2]


def draw_bbox(frame: np.ndarray, bbox: tuple[int, int, int, int], label: str, color: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, label, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
