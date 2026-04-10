"""Main enterprise plate pipeline with multi-vehicle candidate support and privacy rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import cv2

from .blur_pipeline import render_privacy_frame
from .config import PipelineConfig, VEHICLE_MIN_CONFIDENCE
from .curb_detector import CurbDetector
from .debug import draw_plate_box, save_debug_frame
from .ocr_preprocess import preprocess_for_ocr
from .ocr_reader import read_plate_crop
from .ocr_vote import OCRVote
from .plate_cropper import crop_plate, is_crop_ocr_ready
from .plate_detector import PlateDetection, PlateDetector
from .plate_format import classify_plate_format
from .registry_lookup import RegistryLookup
from .result_writer import write_result_json, write_video
from .temporal_blur import TemporalBlurTracker
from .tracker import PlateTracker
from .vehicle_detector import VehicleDetector
from .video_io import get_video_info, read_frames

BBox = tuple[int, int, int, int]


def _dedupe_boxes(detections: list[PlateDetection], max_count: int) -> list[PlateDetection]:
    picked: list[PlateDetection] = []
    for det in sorted(detections, key=lambda d: d.confidence, reverse=True):
        x, y, w, h = det.bbox
        keep = True
        for prev in picked:
            px, py, pw, ph = prev.bbox
            if _iou_xywh((x, y, w, h), (px, py, pw, ph)) > 0.45:
                keep = False
                break
        if keep:
            picked.append(det)
        if len(picked) >= max_count:
            break
    return picked


def _iou_xywh(a: BBox, b: BBox) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    registry = RegistryLookup(cfg.registry_csv)
    vehicle_det = VehicleDetector(model_path=cfg.vehicle_model_path, imgsz=cfg.vehicle_imgsz)
    plate_det = PlateDetector(backend=cfg.detector_backend, yolo_path=cfg.plate_yolo_model_path)
    tracker = PlateTracker(max_misses=cfg.track_max_misses, alpha=cfg.track_smoothing_alpha)
    blur_tracker = TemporalBlurTracker(max_misses=cfg.temporal_blur_max_misses, expand_ratio=cfg.blur_expand_ratio)
    curb_det = CurbDetector()
    ocr_vote = OCRVote()

    frames_out: list = []
    frames_processed = 0
    validated_plate: Optional[str] = None
    selected_ocr: Optional[str] = None
    plate_format_info: Optional[dict] = None
    detector_used = cfg.detector_backend
    debug_dir: Optional[Path] = None
    last_preview_crop = None
    primary_plate_boxes_per_frame: list[Optional[BBox]] = []
    all_plate_boxes_per_frame: list[list[BBox]] = []

    if cfg.debug:
        debug_dir = cfg.output_path.parent / (cfg.output_path.stem + "_debug")
        debug_dir.mkdir(parents=True, exist_ok=True)

    info = get_video_info(cfg.input_path)
    fps = (info or {}).get("fps", 25)

    for frame_idx, frame in read_frames(cfg.input_path, cfg.max_frames):
        vehicles = vehicle_det.detect_and_track(frame)
        vehicles = [v for v in vehicles if v.confidence >= VEHICLE_MIN_CONFIDENCE]

        plate_detections: list[PlateDetection] = []
        if vehicles:
            for vehicle in vehicles:
                x1, y1, x2, y2 = vehicle.bbox
                h_car = y2 - y1
                roi = (x1, y1 + int(h_car * 0.40), x2, y2)
                plate_detections.extend(plate_det.detect(frame, vehicle_roi=roi))
        if not plate_detections:
            plate_detections = plate_det.detect(frame, vehicle_roi=None)

        plate_detections = _dedupe_boxes(plate_detections, cfg.multi_plate_max_per_frame)
        current_boxes = [d.bbox for d in plate_detections]
        all_plate_boxes_per_frame.append(current_boxes)

        detected_box: Optional[BBox] = None
        tracked_plate_box: Optional[BBox] = None
        blur_box: Optional[BBox] = None
        crop = None

        if plate_detections:
            best = max(plate_detections, key=lambda p: p.confidence)
            detected_box = best.bbox
            tracked_plate_box = tracker.update(best.bbox)
            detector_used = best.backend
        else:
            tracked_plate_box = tracker.update(None)

        if cfg.temporal_blur_enabled:
            blur_box = blur_tracker.update(detected_box)
        else:
            blur_box = tracked_plate_box
        primary_plate_boxes_per_frame.append(blur_box)

        ocr_boxes = []
        if tracked_plate_box is not None:
            ocr_boxes.append(tracked_plate_box)
        for box in current_boxes:
            if tracked_plate_box is None or _iou_xywh(box, tracked_plate_box) < 0.45:
                ocr_boxes.append(box)

        for box in ocr_boxes:
            crop = crop_plate(frame, box, cfg.plate_crop_margin_px)
            if crop is None:
                continue
            x, y, w, h = box
            plate_format_info = classify_plate_format(w, h)
            if last_preview_crop is None or (crop.size > 0 and crop.shape[1] * crop.shape[0] >= last_preview_crop.shape[1] * last_preview_crop.shape[0]):
                last_preview_crop = crop.copy()
            should_run_ocr = (
                not cfg.disable_ocr
                and frame_idx % max(1, cfg.ocr_every_n_frames) == 0
                and is_crop_ocr_ready(
                    crop,
                    min_width=cfg.ocr_min_plate_width,
                    min_height=cfg.ocr_min_plate_height,
                    min_sharpness=cfg.ocr_min_sharpness,
                    min_brightness=cfg.ocr_min_brightness,
                    max_brightness=cfg.ocr_max_brightness,
                )
            )
            if should_run_ocr:
                preprocessed = preprocess_for_ocr(
                    crop,
                    resize_factor=cfg.ocr_resize_factor,
                    denoise=cfg.ocr_denoise,
                    sharpen=cfg.ocr_sharpen,
                )
                digits, _ = read_plate_crop(preprocessed)
                if digits:
                    ocr_vote.add(digits)

        preview_text = selected_ocr or validated_plate
        render_boxes = current_boxes[:]
        if blur_box is not None and all(_iou_xywh(blur_box, b) < 0.45 for b in render_boxes):
            render_boxes.append(blur_box)

        out_frame = render_privacy_frame(
            frame,
            render_boxes,
            kernel_size=cfg.blur_kernel_size,
            preview_crop=last_preview_crop if cfg.preview_enabled else None,
            plate_text=preview_text,
            preview_max_w_ratio=cfg.preview_max_w_ratio,
            preview_max_h_ratio=cfg.preview_max_h_ratio,
            preview_margin_px=cfg.preview_margin_px,
            preview_zoom=cfg.preview_zoom,
        )

        if cfg.debug and debug_dir:
            curb_candidates = curb_det.detect(frame)
            curb_overlay = None
            if curb_candidates:
                curb_overlay = frame.copy()
                for c in curb_candidates[:2]:
                    x, y, w, hh = c.bbox
                    cv2.rectangle(curb_overlay, (x, y), (x + w, y + hh), (0, 0, 255), 2)

            overlay = draw_plate_box(frame, tracked_plate_box, (0, 255, 0)) if tracked_plate_box else frame
            save_debug_frame(
                debug_dir,
                frame_idx,
                plate_crop=crop if tracked_plate_box is not None else None,
                preprocessed_crop=preprocess_for_ocr(crop, resize_factor=2) if tracked_plate_box is not None and crop is not None else None,
                overlay=overlay,
                curb_overlay=curb_overlay,
            )

        frames_out.append(out_frame)
        frames_processed += 1

    if not cfg.disable_ocr and ocr_vote.counter:
        selected_ocr = ocr_vote.best_valid(registry.exists) or ocr_vote.best_any()
        if selected_ocr and registry.exists(selected_ocr):
            validated_plate = selected_ocr
        elif selected_ocr:
            validated_plate = selected_ocr

    if selected_ocr and frames_out:
        refreshed_frames: list = []
        for (_, frame), boxes in zip(read_frames(cfg.input_path, cfg.max_frames), all_plate_boxes_per_frame):
            preview_crop = last_preview_crop
            refreshed_frames.append(
                render_privacy_frame(
                    frame,
                    boxes,
                    kernel_size=cfg.blur_kernel_size,
                    preview_crop=preview_crop if cfg.preview_enabled else None,
                    plate_text=selected_ocr,
                    preview_max_w_ratio=cfg.preview_max_w_ratio,
                    preview_max_h_ratio=cfg.preview_max_h_ratio,
                    preview_margin_px=cfg.preview_margin_px,
                    preview_zoom=cfg.preview_zoom,
                )
            )
        frames_out = refreshed_frames

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
            temporal_blur_enabled=cfg.temporal_blur_enabled,
            temporal_blur_max_misses=cfg.temporal_blur_max_misses,
            blur_expand_ratio=cfg.blur_expand_ratio,
            blur_kernel_size=cfg.blur_kernel_size,
            debug_path=str(debug_dir) if debug_dir else None,
            engine_version="enterprise_v2",
            multi_plate_support=True,
        )

    return {
        "validated_plate": validated_plate,
        "registry_match": registry_match,
        "ocr_candidates": ocr_candidates,
        "selected_ocr": selected_ocr,
        "plate_format": plate_format_info,
        "frames_processed": frames_processed,
        "detector_backend": detector_used,
        "temporal_blur_enabled": cfg.temporal_blur_enabled,
        "temporal_blur_max_misses": cfg.temporal_blur_max_misses,
        "blur_expand_ratio": cfg.blur_expand_ratio,
        "blur_kernel_size": cfg.blur_kernel_size,
        "engine_version": "enterprise_v2",
        "multi_plate_support": True,
    }
