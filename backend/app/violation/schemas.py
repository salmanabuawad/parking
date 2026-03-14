"""Violation detection schemas (from ref pipeline)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BBox = tuple[int, int, int, int]


@dataclass
class Detection:
    bbox: BBox
    confidence: float
    class_name: str
    track_id: int | None = None


@dataclass
class PlateRead:
    text: str
    confidence: float
    bbox: BBox


@dataclass
class VehicleRegistryRecord:
    plate_number: str
    manufacturer: str | None = None
    model_name: str | None = None
    production_year: int | None = None
    model_code: str | None = None
    tyre_spec: str | None = None
    raw: dict[str, Any] = None

    def __post_init__(self):
        if self.raw is None:
            self.raw = {}


@dataclass
class VehicleDimensions:
    manufacturer: str
    model_name: str
    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    wheelbase_m: float | None = None


@dataclass
class ScaleEstimate:
    method: str
    meters_per_pixel: float | None
    confidence: float
    details: dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class CurbCandidate:
    bbox: tuple[int, int, int, int]
    score: float
    angle_deg: float
    contour_points: list[tuple[int, int]] = None
    block_length_px: float | None = None
    curb_width_px: float | None = None

    def __post_init__(self):
        if self.contour_points is None:
            self.contour_points = []


@dataclass
class DistanceEstimate:
    gap_px: float
    gap_m: float | None
    scale_method: str | None
    scale_confidence: float | None


@dataclass
class VehicleDecision:
    vehicle: Detection
    plate: PlateRead | None
    registry_record: VehicleRegistryRecord | None
    dimensions: VehicleDimensions | None
    tyre_scale: ScaleEstimate | None
    curb: CurbCandidate | None
    distance: DistanceEstimate | None
    stationary_frames: int
    should_unblur: bool
    reason: str


@dataclass
class FrameResult:
    frame_index: int
    decisions: list[VehicleDecision]
