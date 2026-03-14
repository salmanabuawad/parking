"""Distance estimation from vehicle to curb."""
from __future__ import annotations

from app.violation.schemas import CurbCandidate, Detection, DistanceEstimate, ScaleEstimate, VehicleDimensions
from app.violation.utils.geometry import bbox_bottom_center, bbox_width, min_distance_points_to_rect


class DistanceEstimator:
    def vehicle_scale(self, vehicle: Detection, dimensions: VehicleDimensions | None) -> ScaleEstimate | None:
        if dimensions is None or dimensions.width_m is None:
            return None
        width_px = bbox_width(vehicle.bbox)
        if width_px <= 0:
            return None
        return ScaleEstimate(
            method='vehicle-width',
            meters_per_pixel=dimensions.width_m / width_px,
            confidence=0.62,
            details={'vehicle_width_m': dimensions.width_m, 'vehicle_width_px': width_px},
        )

    def curb_scale(self, curb: CurbCandidate | None) -> ScaleEstimate | None:
        if curb is None or curb.block_length_px is None or curb.block_length_px <= 0:
            return None
        return ScaleEstimate(
            method='curb-block',
            meters_per_pixel=1.0 / curb.block_length_px,
            confidence=0.55,
            details={'block_length_px': curb.block_length_px, 'assumed_block_length_m': 1.0},
        )

    def choose_scale(self, tyre_scale: ScaleEstimate | None, vehicle_scale: ScaleEstimate | None, curb_scale: ScaleEstimate | None) -> ScaleEstimate | None:
        choices = [s for s in [tyre_scale, vehicle_scale, curb_scale] if s and s.meters_per_pixel]
        if not choices:
            return None
        choices.sort(key=lambda s: s.confidence, reverse=True)
        return choices[0]

    def estimate(self, vehicle: Detection, curb: CurbCandidate | None, chosen_scale: ScaleEstimate | None) -> DistanceEstimate | None:
        if curb is None:
            return None
        x1, y1, x2, y2 = vehicle.bbox
        points = [(x1, y2), (x2, y2), bbox_bottom_center(vehicle.bbox)]
        gap_px = min_distance_points_to_rect(points, curb.bbox)
        gap_m = None if chosen_scale is None or chosen_scale.meters_per_pixel is None else gap_px * chosen_scale.meters_per_pixel
        return DistanceEstimate(
            gap_px=float(gap_px),
            gap_m=float(gap_m) if gap_m is not None else None,
            scale_method=None if chosen_scale is None else chosen_scale.method,
            scale_confidence=None if chosen_scale is None else chosen_scale.confidence,
        )
