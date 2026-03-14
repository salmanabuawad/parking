"""
Main pipeline: vehicle-first, plate detection, tracking, OCR vote, registry validation, blur.
Thin orchestration; logic lives in modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from .blur_pipeline import blur_except_plate
from .config import PipelineConfig, VEHICLE_MIN_CONFIDENCE
from .curb_detector import CurbDetector
from .debug import draw_plate_box, save_debug_frame
from .ocr_preprocess import preprocess_for_ocr
from .ocr_reader import read_plate_crop
from .ocr_vote import OCRVote
from .plate_cropper import crop_plate
from .plate_detector import PlateDetection, PlateDetector
from .plate_format import classify_plate_format
from .registry_lookup import RegistryLookup
from .result_writer import write_result_json, write_video
from .tracker import PlateTracker
from .vehicle_detector import VehicleDetector
from .video_io import get_video_info, read_frames


def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    """
    Process video: detect vehicles, plates, OCR vote, registry validate, blur.
    Returns result dict for JSON output.
    """
    registry = RegistryLookup(cfg.registry_csv)
    vehicle_det = VehicleDetector()
    plate_det = PlateDetector(backend=cfg.detector_backend)
    tracker = PlateTracker(max_misses=cfg.track_max_misses, alpha=cfg.track_smoothing_alpha)
    curb_det = CurbDetector()

    ocr_vote = OCRVote()
    frames_out: list[np.ndarray] = []
    frames_processed = 0
    validated_plate: Optional[str] = None
    selected_ocr: Optional[str] = None
    plate_format_info: Optional[dict] = None
    detector_used = cfg.detector_backend
    debug_dir: Optional[Path] = None
    if cfg.debug:
        debug_dir = cfg.output_path.parent / (cfg.output_path.stem + "_debug")
        debug_dir.mkdir(parents=True, exist_ok=True)

    info = get_video_info(cfg.input_path)
    fps = (info or {}).get("fps", 25)

    last_plate_box: Optional[tuple[int, int, int, int]] = None
    last_plate_crop: Optional[np.ndarray] = None
    plate_boxes_per_frame: list[Optional[tuple[int, int, int, int]]] = []

    for frame_idx, frame in read_frames(cfg.input_path, cfg.max_frames):
        # 1. Vehicle-first: detect vehicles
        vehicles = vehicle_det.detect(frame)
        vehicles = [v for v in vehicles if v.confidence >= VEHICLE_MIN_CONFIDENCE]
        primary_vehicle = max(vehicles, key=lambda v: (v.bbox[2] - v.bbox[0]) * (v.bbox[3] - v.bbox[1])) if vehicles else None

        # 2. Plate detection: in vehicle ROI or full frame fallback
        roi: Optional[tuple[int, int, int, int]] = None
        if primary_vehicle:
            x1, y1, x2, y2 = primary_vehicle.bbox
            h_car = y2 - y1
            roi = (x1, y1 + int(h_car * 0.5), x2, y2)
        plate_detections = plate_det.detect(frame, vehicle_roi=roi)
        if not plate_detections and primary_vehicle is None:
            plate_detections = plate_det.detect(frame, vehicle_roi=None)

        # 3. Pick best plate, track
        plate_box: Optional[tuple[int, int, int, int]] = None
        if plate_detections:
            best = max(plate_detections, key=lambda p: p.confidence)
            plate_box = tracker.update(best.bbox)
        else:
            plate_box = tracker.update(None)

        # Always blur fully during first pass; we validate at end
        if plate_box is not None:
            # 4. Crop plate (tight only)
            crop = crop_plate(frame, plate_box, cfg.plate_crop_margin_px)
            if crop is not None:
                last_plate_crop = crop
                last_plate_box = plate_box

                # 5. OCR on tight crop only (optional)
                if not cfg.disable_ocr:
                    preprocessed = preprocess_for_ocr(
                        crop,
                        resize_factor=cfg.ocr_resize_factor,
                        denoise=cfg.ocr_denoise,
                        sharpen=cfg.ocr_sharpen,
                    )
                    digits, _ = read_plate_crop(preprocessed)
                    if digits:
                        ocr_vote.add(digits)

                # 6. Plate format
                x, y, w, h = plate_box
                plate_format_info = classify_plate_format(w, h)
                plate_boxes_per_frame.append(plate_box)
            else:
                plate_boxes_per_frame.append(None)
        else:
            plate_boxes_per_frame.append(None)

        out_frame = blur_except_plate(frame, None, cfg.blur_kernel_size)

        # Debug
        if cfg.debug and debug_dir:
            curb_candidates = curb_det.detect(frame)
            curb_overlay = None
            if curb_candidates:
                curb_overlay = frame.copy()
                for c in curb_candidates[:2]:
                    x, y, w, hh = c.bbox
                    cv2.rectangle(curb_overlay, (x, y), (x + w, y + hh), (0, 0, 255), 2)
            overlay = draw_plate_box(frame, plate_box, (0, 255, 0)) if plate_box else frame
            save_debug_frame(
                debug_dir,
                frame_idx,
                plate_crop=last_plate_crop,
                preprocessed_crop=preprocess_for_ocr(last_plate_crop, resize_factor=2) if last_plate_crop else None,
                overlay=overlay,
                curb_overlay=curb_overlay,
            )

        frames_out.append(out_frame)
        frames_processed += 1

    # 8. OCR vote + registry validation
    if not cfg.disable_ocr and ocr_vote.counter:
        selected_ocr = ocr_vote.best_valid(registry.exists)
        if selected_ocr and registry.exists(selected_ocr):
            validated_plate = selected_ocr

    # 9. If validated plate exists, second pass: restore plate regions
    if validated_plate and plate_boxes_per_frame:
        frames_out = []
        for (_, frame), plate_box in zip(read_frames(cfg.input_path, cfg.max_frames), plate_boxes_per_frame):
            frames_out.append(blur_except_plate(frame, plate_box, cfg.blur_kernel_size))

    # 10. Write output
    write_video(frames_out, cfg.output_path, fps=fps)
    ocr_candidates = ocr_vote.all_candidates()
    registry_match = registry.get(validated_plate) if validated_plate else None

    if cfg.output_json:
        json_path = cfg.output_path.with_suffix(".json")
        write_result_json(
            json_path,
            validated_plate=validated_plate,
            registry_match=registry_match,
            ocr_candidates=ocr_candidates,
            selected_ocr=selected_ocr,
            plate_format=plate_format_info,
            frames_processed=frames_processed,
            detector_backend=detector_used,
            debug_path=str(debug_dir) if debug_dir else None,
        )

    return {
        "validated_plate": validated_plate,
        "registry_match": registry_match,
        "ocr_candidates": ocr_candidates,
        "selected_ocr": selected_ocr,
        "plate_format": plate_format_info,
        "frames_processed": frames_processed,
        "detector_backend": detector_used,
    }
