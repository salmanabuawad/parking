"""
Distance estimation scaffold for future curb-distance measurement.
"""
from __future__ import annotations

from dataclasses import dataclass

from .curb_detector import CurbCandidate


@dataclass
class ScaleEstimate:
    method: str
    meters_per_pixel: float | None
    confidence: float


@dataclass
class DistanceEstimate:
    gap_px: float | None
    gap_m: float | None
    scale_method: str | None


class DistanceEstimator:
    """Placeholder for future scale and distance estimation."""

    def curb_scale(self, curb: CurbCandidate | None) -> ScaleEstimate | None:
        if curb is None:
            return None
        return ScaleEstimate(method="curb-scaffold", meters_per_pixel=None, confidence=0.0)

    def estimate(self, vehicle_bbox: tuple, curb: CurbCandidate | None, scale: ScaleEstimate | None) -> DistanceEstimate | None:
        return DistanceEstimate(gap_px=None, gap_m=None, scale_method=None)
