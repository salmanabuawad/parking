"""Red/white curb detection."""
from __future__ import annotations

import cv2
import numpy as np

from app.violation.schemas import CurbCandidate


class CurbDetector:
    def _masks(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 80, 60], dtype=np.uint8)
        upper_red1 = np.array([12, 255, 255], dtype=np.uint8)
        lower_red2 = np.array([165, 80, 60], dtype=np.uint8)
        upper_red2 = np.array([180, 255, 255], dtype=np.uint8)
        lower_white = np.array([0, 0, 170], dtype=np.uint8)
        upper_white = np.array([180, 70, 255], dtype=np.uint8)
        red = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))
        white = cv2.inRange(hsv, lower_white, upper_white)
        return red, white

    def _clean(self, mask):
        k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k2)
        return mask

    def detect(self, frame) -> list[CurbCandidate]:
        red, white = self._masks(frame)
        red = self._clean(red)
        white = self._clean(white)
        merged = self._clean(cv2.bitwise_or(red, white))
        contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, _ = frame.shape[:2]
        candidates: list[CurbCandidate] = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 800:
                continue
            x, y, w, hh = cv2.boundingRect(cnt)
            aspect = max(w, hh) / max(1, min(w, hh))
            if aspect < 2.5:
                continue
            rect = cv2.minAreaRect(cnt)
            (_, _), (rw, rh), angle = rect
            long_side = max(rw, rh)
            short_side = min(rw, rh)
            roi_red = red[y:y+hh, x:x+w]
            roi_white = white[y:y+hh, x:x+w]
            red_pixels = int(np.count_nonzero(roi_red))
            white_pixels = int(np.count_nonzero(roi_white))
            if red_pixels < 50 or white_pixels < 50:
                continue
            score = 0.0
            score += min(red_pixels, white_pixels) / max(1, red_pixels + white_pixels)
            score += min(aspect / 8.0, 1.0)
            score += (y + hh / 2.0) / h
            points = cv2.boxPoints(rect).astype(int).tolist()
            candidates.append(CurbCandidate(
                bbox=(x, y, w, hh),
                score=float(score),
                angle_deg=float(angle),
                contour_points=[tuple(p) for p in points],
                block_length_px=long_side / 4.0 if long_side > 0 else None,
                curb_width_px=short_side if short_side > 0 else None,
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:5]
