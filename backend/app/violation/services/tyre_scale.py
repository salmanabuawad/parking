"""Tyre-based scale estimation from registry tyre spec."""
from __future__ import annotations

import re
import cv2

from app.violation.schemas import Detection, ScaleEstimate, VehicleRegistryRecord
from app.violation.utils.image import crop_bbox


class TyreScaleEstimator:
    TYRE_RE = re.compile(r'(\d{3})\s*/\s*(\d{2})\s*R\s*(\d{2})', re.IGNORECASE)

    def parse_tyre_spec(self, value: str | None) -> float | None:
        if not value:
            return None
        m = self.TYRE_RE.search(value.replace('-', '').replace(' ', ''))
        if not m:
            m = self.TYRE_RE.search(value)
        if not m:
            return None
        width_mm = float(m.group(1))
        aspect = float(m.group(2))
        rim_in = float(m.group(3))
        sidewall_mm = width_mm * (aspect / 100.0)
        rim_mm = rim_in * 25.4
        return (rim_mm + 2 * sidewall_mm) / 1000.0

    def detect_wheel_diameter_px(self, frame, vehicle: Detection) -> float | None:
        roi = crop_bbox(frame, vehicle.bbox)
        if roi.size == 0:
            return None
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1.2,
            minDist=max(20, roi.shape[1] // 6), param1=100, param2=24,
            minRadius=max(10, roi.shape[0] // 12), maxRadius=max(20, roi.shape[0] // 3),
        )
        if circles is None:
            return None
        largest = max(circles[0], key=lambda c: c[2])
        return float(largest[2]) * 2.0

    def estimate(self, frame, vehicle: Detection, registry_record: VehicleRegistryRecord | None) -> ScaleEstimate | None:
        if registry_record is None:
            return None
        tyre_diameter_m = self.parse_tyre_spec(registry_record.tyre_spec)
        if tyre_diameter_m is None:
            return None
        wheel_diameter_px = self.detect_wheel_diameter_px(frame, vehicle)
        if not wheel_diameter_px or wheel_diameter_px <= 0:
            return None
        mpp = tyre_diameter_m / wheel_diameter_px
        return ScaleEstimate(
            method='tyre-diameter',
            meters_per_pixel=mpp,
            confidence=0.72,
            details={'tyre_spec': registry_record.tyre_spec, 'tyre_diameter_m': tyre_diameter_m, 'wheel_diameter_px': wheel_diameter_px},
        )
