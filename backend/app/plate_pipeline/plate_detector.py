"""
Plate detector with pluggable backends.
Primary: YOLO plate detector (when available).
Fallback: HSV yellow segmentation.
Returns bbox, confidence, source backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

import cv2
import numpy as np

from .config import (
    HSV_LOWER_LIGHT,
    HSV_LOWER_YELLOW,
    HSV_UPPER_LIGHT,
    HSV_UPPER_YELLOW,
    MAX_PLATE_AREA_RATIO,
    MIN_PLATE_AREA,
    PLATE_FORMAT_PRESETS,
    PLATE_MAX_RATIO,
    PLATE_MIN_RATIO,
)


@dataclass
class PlateDetection:
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    backend: Literal["yolo", "hsv"]


class PlateDetector:
    """
    Unified plate detector interface.
    Backend: "yolo" (primary) or "hsv" (fallback).
    """

    def __init__(self, backend: Literal["yolo", "hsv"] = "hsv", yolo_path: str | None = None):
        self.backend = backend
        self.yolo_path = yolo_path or "yolov8n.pt"
        self._yolo = None

    def detect(
        self,
        frame: np.ndarray,
        vehicle_roi: Tuple[int, int, int, int] | None = None,
    ) -> List[PlateDetection]:
        """
        Detect plates. If vehicle_roi (x1,y1,x2,y2) given, search only inside it.
        """
        if self.backend == "yolo":
            return self._detect_yolo(frame, vehicle_roi)
        return self._detect_hsv(frame, vehicle_roi)

    def _detect_yolo(self, frame: np.ndarray, roi: Tuple[int, int, int, int] | None) -> List[PlateDetection]:
        # TODO: Load YOLO plate model when available; for now fallback to HSV
        return self._detect_hsv(frame, roi)

    def _detect_hsv(
        self,
        frame: np.ndarray,
        roi: Tuple[int, int, int, int] | None,
    ) -> List[PlateDetection]:
        if roi:
            x1, y1, x2, y2 = roi
            region = frame[y1:y2, x1:x2]
            boxes = _hsv_detect_plates(region)
            # Convert to full-frame coords
            out: List[PlateDetection] = []
            for (rx, ry, rw, rh), conf in boxes:
                out.append(PlateDetection(
                    bbox=(x1 + rx, y1 + ry, rw, rh),
                    confidence=conf,
                    backend="hsv",
                ))
            return out
        boxes = _hsv_detect_plates(frame)
        return [PlateDetection(bbox=b, confidence=c, backend="hsv") for b, c in boxes]


def _hsv_detect_plates(frame: np.ndarray) -> List[Tuple[Tuple[int, int, int, int], float]]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(HSV_LOWER_YELLOW, dtype=np.uint8), np.array(HSV_UPPER_YELLOW, dtype=np.uint8))
    mask_light = cv2.inRange(hsv, np.array(HSV_LOWER_LIGHT, dtype=np.uint8), np.array(HSV_UPPER_LIGHT, dtype=np.uint8))
    mask = cv2.bitwise_or(mask, mask_light)
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_area = frame.shape[0] * frame.shape[1]
    candidates: List[Tuple[Tuple[int, int, int, int], float]] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        ratio = w / h if h > 0 else 0
        if area < MIN_PLATE_AREA:
            continue
        if not (PLATE_MIN_RATIO < ratio < PLATE_MAX_RATIO):
            continue
        if area > frame_area * MAX_PLATE_AREA_RATIO:
            continue
        aspect_fit = min(1.0, max(0, 1.0 - min(abs(ratio - p["ratio"]) for p in PLATE_FORMAT_PRESETS) / 2.0))
        compact = cv2.contourArea(cnt) / area if area > 0 else 0
        score = area * (0.5 + aspect_fit) * (0.5 + min(1.0, compact))
        candidates.append(((x, y, w, h), min(1.0, score / 5000)))
    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[:5]
