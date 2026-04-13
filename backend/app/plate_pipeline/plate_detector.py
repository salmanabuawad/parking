"""Plate detector with pluggable backends.

Primary: YOLO plate detector when a dedicated model is available.
Fallback: improved HSV + geometry + edge-density candidate scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
    PLATE_DETECT_TOP_K,
    PLATE_FORMAT_PRESETS,
    PLATE_MAX_RATIO,
    PLATE_MIN_RATIO,
    ROI_HORIZONTAL_EXPAND,
    ROI_VERTICAL_EXPAND,
)

BBox = Tuple[int, int, int, int]
XYXY = Tuple[int, int, int, int]


@dataclass
class PlateDetection:
    bbox: BBox  # x, y, w, h
    confidence: float
    backend: Literal["yolo", "hsv"]


class PlateDetector:
    """Unified plate detector interface."""

    def __init__(self, backend: Literal["yolo", "hsv"] = "hsv", yolo_path: str | None = None):
        self.backend = backend
        self.yolo_path = yolo_path or "yolov8n.pt"
        self._yolo = None
        self._yolo_failed = False

    def detect(
        self,
        frame: np.ndarray,
        vehicle_roi: XYXY | None = None,
    ) -> List[PlateDetection]:
        if self.backend == "yolo":
            yolo_hits = self._detect_yolo(frame, vehicle_roi)
            if yolo_hits:
                return yolo_hits
        return self._detect_hsv(frame, vehicle_roi)

    def _get_yolo(self):
        if self._yolo_failed:
            return None
        if self._yolo is None:
            try:
                from ultralytics import YOLO

                if not Path(self.yolo_path).exists():
                    self._yolo_failed = True
                    return None
                self._yolo = YOLO(self.yolo_path)
            except Exception:
                self._yolo_failed = True
                return None
        return self._yolo

    def _detect_yolo(self, frame: np.ndarray, roi: XYXY | None) -> List[PlateDetection]:
        model = self._get_yolo()
        if model is None:
            return []

        crop = frame
        offset_x = offset_y = 0
        if roi is not None:
            x1, y1, x2, y2 = _expand_roi(frame.shape, roi)
            crop = frame[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1

        if crop.size == 0:
            return []

        try:
            results = model.predict(crop, verbose=False)
        except Exception:
            self._yolo_failed = True
            return []

        detections: List[PlateDetection] = []
        for r in results:
            if getattr(r, "boxes", None) is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                w, h = x2 - x1, y2 - y1
                if w <= 0 or h <= 0:
                    continue
                ratio = w / h
                if not (PLATE_MIN_RATIO <= ratio <= PLATE_MAX_RATIO):
                    continue
                conf = float(box.conf[0].item()) if box.conf is not None else 0.0
                detections.append(
                    PlateDetection(
                        bbox=(offset_x + x1, offset_y + y1, w, h),
                        confidence=conf,
                        backend="yolo",
                    )
                )
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[:PLATE_DETECT_TOP_K]

    def _detect_hsv(
        self,
        frame: np.ndarray,
        roi: XYXY | None,
    ) -> List[PlateDetection]:
        if roi:
            x1, y1, x2, y2 = _expand_roi(frame.shape, roi)
            region = frame[y1:y2, x1:x2]
            boxes = _hsv_detect_plates(region)
            out: List[PlateDetection] = []
            for (rx, ry, rw, rh), conf in boxes:
                out.append(
                    PlateDetection(
                        bbox=(x1 + rx, y1 + ry, rw, rh),
                        confidence=conf,
                        backend="hsv",
                    )
                )
            return out
        boxes = _hsv_detect_plates(frame)
        return [PlateDetection(bbox=b, confidence=c, backend="hsv") for b, c in boxes]


def _expand_roi(shape: tuple[int, ...], roi: XYXY) -> XYXY:
    x1, y1, x2, y2 = roi
    h, w = shape[:2]
    pad_x = int((x2 - x1) * ROI_HORIZONTAL_EXPAND)
    pad_y = int((y2 - y1) * ROI_VERTICAL_EXPAND)
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(w, x2 + pad_x),
        min(h, y2 + pad_y),
    )


def _hsv_detect_plates(frame: np.ndarray) -> List[Tuple[BBox, float]]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Yellow mask only — the wide "light" mask caused massive false positives
    # on roads, walls and other bright surfaces.
    mask = cv2.inRange(hsv, np.array(HSV_LOWER_YELLOW, dtype=np.uint8), np.array(HSV_UPPER_YELLOW, dtype=np.uint8))

    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k2)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 180)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_h, frame_w = frame.shape[:2]
    frame_area = frame_h * frame_w
    candidates: List[Tuple[BBox, float]] = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        ratio = w / h if h > 0 else 0
        if area < MIN_PLATE_AREA:
            continue
        if area > frame_area * MAX_PLATE_AREA_RATIO:
            continue
        if not (PLATE_MIN_RATIO <= ratio <= PLATE_MAX_RATIO):
            continue
        if y > int(frame_h * 0.95):
            continue

        roi_edges = edges[y : y + h, x : x + w]
        edge_density = float(np.count_nonzero(roi_edges)) / float(area)
        fill_ratio = float(cv2.contourArea(cnt)) / float(area) if area > 0 else 0.0
        rect_score = _rectangularity(cnt)
        aspect_fit = min(
            1.0,
            max(0.0, 1.0 - min(abs(ratio - p["ratio"]) for p in PLATE_FORMAT_PRESETS) / 2.5),
        )

        score = (
            0.34 * aspect_fit
            + 0.24 * min(1.0, fill_ratio)
            + 0.22 * min(1.0, edge_density * 3.0)
            + 0.20 * rect_score
        )
        if score < 0.35:
            continue
        candidates.append(((x, y, w, h), float(score)))

    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[:PLATE_DETECT_TOP_K]


def _rectangularity(cnt: np.ndarray) -> float:
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
    if len(approx) == 4:
        return 1.0
    return max(0.0, 1.0 - abs(len(approx) - 4) * 0.2)
