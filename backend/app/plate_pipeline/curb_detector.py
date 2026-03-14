"""
Red/white curb detection scaffold.
Returns curb candidates and debug overlays. No legal decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from .config import CURB_MIN_AREA


@dataclass
class CurbCandidate:
    bbox: tuple[int, int, int, int]
    score: float
    angle_deg: float
    contour_points: list[tuple[int, int]]


class CurbDetector:
    """Detect red/white curb stripe candidates for future distance work."""

    def __init__(self):
        self._lower_red1 = np.array([0, 80, 60], dtype=np.uint8)
        self._upper_red1 = np.array([12, 255, 255], dtype=np.uint8)
        self._lower_red2 = np.array([165, 80, 60], dtype=np.uint8)
        self._upper_red2 = np.array([180, 255, 255], dtype=np.uint8)
        self._lower_white = np.array([0, 0, 170], dtype=np.uint8)
        self._upper_white = np.array([180, 70, 255], dtype=np.uint8)

    def detect(self, frame: np.ndarray) -> List[CurbCandidate]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        red = cv2.bitwise_or(
            cv2.inRange(hsv, self._lower_red1, self._upper_red1),
            cv2.inRange(hsv, self._lower_red2, self._upper_red2),
        )
        white = cv2.inRange(hsv, self._lower_white, self._upper_white)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        red = cv2.morphologyEx(red, cv2.MORPH_OPEN, k)
        white = cv2.morphologyEx(white, cv2.MORPH_OPEN, k)
        merged = cv2.morphologyEx(cv2.bitwise_or(red, white), cv2.MORPH_CLOSE, k)
        contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, _ = frame.shape[:2]
        candidates: List[CurbCandidate] = []
        for cnt in contours:
            if cv2.contourArea(cnt) < CURB_MIN_AREA:
                continue
            x, y, w, hh = cv2.boundingRect(cnt)
            aspect = max(w, hh) / max(1, min(w, hh))
            if aspect < 2.5:
                continue
            rect = cv2.minAreaRect(cnt)
            (_, _), (_, _), angle = rect
            roi_red = red[y : y + hh, x : x + w]
            roi_white = white[y : y + hh, x : x + w]
            rp, wp = int(np.count_nonzero(roi_red)), int(np.count_nonzero(roi_white))
            if rp < 50 or wp < 50:
                continue
            score = min(rp, wp) / max(1, rp + wp) + min(aspect / 8.0, 1.0) + (y + hh / 2) / h
            pts = cv2.boxPoints(rect).astype(int).tolist()
            candidates.append(CurbCandidate(
                bbox=(x, y, w, hh),
                score=float(score),
                angle_deg=float(angle),
                contour_points=[tuple(p) for p in pts],
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:5]
