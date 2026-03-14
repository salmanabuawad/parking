"""Parking violation pipeline: vehicle detection, curb distance, selective blur."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from app.config import settings
from app.violation.schemas import FrameResult, VehicleDecision
from app.violation.services.blur import BlurService
from app.violation.services.curb_detector import CurbDetector
from app.violation.services.detector import VehicleDetector
from app.violation.services.dimensions import VehicleDimensionProvider
from app.violation.services.distance import DistanceEstimator
from app.violation.services.plate_ocr import PlateOCRService
from app.violation.services.registry import VehicleRegistryService
from app.violation.services.evidence import EvidenceService
from app.violation.services.tyre_scale import TyreScaleEstimator
from app.violation.utils.image import draw_bbox


class ParkingViolationPipeline:
    """Process video frames: detect vehicles, measure curb distance, selectively blur.
    Uses 10s-interval parked zones: cars at same location in samples 10s apart = parked."""

    def __init__(self, output_dir: str | Path | None = None, parked_zones: list[tuple[float, float, float]] | None = None):
        self.detector = VehicleDetector(getattr(settings, 'yolo_model_path', 'yolov8n.pt'))
        self.ocr = PlateOCRService()
        self.registry = VehicleRegistryService()
        self.dimensions = VehicleDimensionProvider()
        self.tyre_scale = TyreScaleEstimator()
        self.curb_detector = CurbDetector()
        self.distance = DistanceEstimator()
        self.blur = BlurService()
        self.stationary_frames: dict[int, int] = defaultdict(int)
        self.last_boxes: dict[int, tuple[int, int, int, int]] = {}
        self.evidence = EvidenceService(output_dir, getattr(settings, 'save_evidence_frames', True)) if output_dir else None
        self.parked_zones = parked_zones or []
        self._inference_interval = getattr(settings, 'yolo_inference_interval', 1)  # 1=every frame, 5=every 5th
        self._cached_keep_boxes: list[tuple[int, int, int, int]] = []
        self._cached_decisions: list = []

    def _is_in_parked_zone(self, bbox: tuple[int, int, int, int]) -> bool:
        """True if vehicle center is within any 10s-interval parked zone."""
        if not self.parked_zones:
            return False
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        for px, py, r in self.parked_zones:
            if (cx - px) ** 2 + (cy - py) ** 2 <= r ** 2:
                return True
        return False

    def _update_stationary(self, track_id: int | None, bbox: tuple[int, int, int, int]) -> int:
        if track_id is None:
            return 0
        prev = self.last_boxes.get(track_id)
        self.last_boxes[track_id] = bbox
        if prev is None:
            self.stationary_frames[track_id] = 1
            return 1
        movement = sum(abs(a - b) for a, b in zip(prev, bbox)) / 4.0
        if movement <= 6.0:
            self.stationary_frames[track_id] += 1
        else:
            self.stationary_frames[track_id] = 1
        return self.stationary_frames[track_id]

    def process_frame(self, frame, frame_index: int):
        # Skip YOLO + curb + distance every Nth frame; reuse cached keep_boxes (major speedup)
        run_inference = (frame_index - 1) % self._inference_interval == 0
        if not run_inference:
            output = self.blur.selectively_unblur(frame, self._cached_keep_boxes)
            return output, FrameResult(frame_index=frame_index, decisions=self._cached_decisions)

        vehicles = self.detector.detect_and_track(frame)
        curbs = self.curb_detector.detect(frame)
        best_curb = curbs[0] if curbs else None

        decisions: list[VehicleDecision] = []
        keep_boxes: list[tuple[int, int, int, int]] = []
        max_dist = getattr(settings, 'max_car_curb_distance_m', 0.50)
        min_stationary = getattr(settings, 'min_stationary_frames', 12)

        for vehicle in vehicles:
            plate = self.ocr.read_plate_from_vehicle(frame, vehicle)
            registry_record = self.registry.lookup(plate.text) if plate else None
            dims = self.dimensions.get_dimensions(registry_record)
            tyre_scale = self.tyre_scale.estimate(frame, vehicle, registry_record)
            vehicle_scale = self.distance.vehicle_scale(vehicle, dims)
            curb_scale = self.distance.curb_scale(best_curb)
            chosen_scale = self.distance.choose_scale(tyre_scale, vehicle_scale, curb_scale)
            distance = self.distance.estimate(vehicle, best_curb, chosen_scale)
            stationary_frames = self._update_stationary(vehicle.track_id, vehicle.bbox)
            in_parked_zone = self._is_in_parked_zone(vehicle.bbox)

            should_unblur = False
            reason = 'no qualifying rule'
            if best_curb is None:
                reason = 'curb not detected'
            elif distance is None or distance.gap_m is None:
                reason = 'distance unavailable'
            elif distance.gap_m > max_dist:
                reason = f'too far from curb: {distance.gap_m:.2f}m'
            elif in_parked_zone or stationary_frames >= min_stationary:
                should_unblur = True
                reason = f'within curb distance ({distance.gap_m:.2f}m) and parked ({"10s-interval" if in_parked_zone else "frame tracking"})'
                keep_boxes.append(vehicle.bbox)
            elif stationary_frames < min_stationary:
                reason = f'not stationary long enough: {stationary_frames} frames'

            decision = VehicleDecision(
                vehicle=vehicle,
                plate=plate,
                registry_record=registry_record,
                dimensions=dims,
                tyre_scale=tyre_scale,
                curb=best_curb,
                distance=distance,
                stationary_frames=stationary_frames,
                should_unblur=should_unblur,
                reason=reason,
            )
            decisions.append(decision)

        self._cached_keep_boxes = keep_boxes
        self._cached_decisions = decisions
        self._cached_keep_boxes = keep_boxes
        self._cached_decisions = decisions
        output = self.blur.selectively_unblur(frame, keep_boxes)

        if getattr(settings, 'debug_draw', False):
            if best_curb:
                x, y, w, h = best_curb.bbox
                draw_bbox(output, (x, y, x + w, y + h), 'curb', (0, 255, 255))
            for decision in decisions:
                label = decision.reason[:90]
                if decision.plate:
                    label = f"{decision.plate.text} | {label}"
                color = (0, 255, 0) if decision.should_unblur else (0, 0, 255)
                draw_bbox(output, decision.vehicle.bbox, label, color)

        evidence_path = None
        if self.evidence and any(d.should_unblur for d in decisions):
            evidence_path = self.evidence.save_frame(frame_index, output)

        return output, FrameResult(frame_index=frame_index, decisions=decisions)
