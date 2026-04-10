"""Main enterprise plate pipeline with multi-vehicle candidate support and privacy rendering.

Design notes
------------
* OCR runs on RAW BGR crops from the original (unblurred) frame.
  `preprocess_for_ocr` is NOT called here — all preprocessing is inside
  `read_plate_crop` / `_ocr_variants` so there is no double-processing.
* Best crop (by Laplacian sharpness) is tracked across all frames and an
  additional OCR pass is run on it at the end if we still have no result.
* EasyOCR is tried as fallback inside `read_plate_crop` automatically.
* Comprehensive logging at every decision point.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from .blur_pipeline import render_privacy_frame
from .config import PipelineConfig, VEHICLE_MIN_CONFIDENCE
from .curb_detector import CurbDetector
from .debug import draw_plate_box, save_debug_frame
from .ocr_reader import read_plate_crop, clean_plate_text
from .ocr_vote import OCRVote
from .plate_cropper import crop_plate, is_crop_ocr_ready, estimate_crop_quality
from .plate_detector import PlateDetection, PlateDetector
from .plate_format import classify_plate_format
from .registry_lookup import RegistryLookup
from .result_writer import write_result_json, write_video
from .temporal_blur import TemporalBlurTracker
from .tracker import PlateTracker
from .vehicle_detector import VehicleDetector
from .video_io import get_video_info, read_frames

BBox = tuple[int, int, int, int]


# ── helpers ────────────────────────────────────────────────────────────────

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


def _sharpness(crop: np.ndarray) -> float:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


# ── main pipeline ──────────────────────────────────────────────────────────

def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    print(
        f"[pipeline] START  detector={cfg.detector_backend}  "
        f"ocr={'disabled' if cfg.disable_ocr else 'enabled'}  "
        f"max_frames={cfg.max_frames}  ocr_every={cfg.ocr_every_n_frames}  "
        f"yolo_every={cfg.yolo_every_n_frames}",
        flush=True,
    )

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

    # Best-crop tracking (by sharpness)
    best_crop: Optional[np.ndarray] = None
    best_crop_sharpness: float = -1.0
    best_crop_frame: int = -1

    # Debug log accumulator
    debug_log: list[dict] = []

    if cfg.debug:
        debug_dir = cfg.output_path.parent / (cfg.output_path.stem + "_debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        print(f"[pipeline] debug dir: {debug_dir}", flush=True)

    info = get_video_info(cfg.input_path)
    fps = (info or {}).get("fps", 25)
    print(f"[pipeline] video info: {info}", flush=True)

    # Cache last YOLO vehicle result — reuse across skipped frames
    last_vehicles: list = []
    yolo_every = max(1, getattr(cfg, "yolo_every_n_frames", 3))

    for frame_idx, frame in read_frames(cfg.input_path, cfg.max_frames):

        # ── YOLO vehicle detection: only every N frames ────────────────────
        if frame_idx % yolo_every == 0:
            last_vehicles = vehicle_det.detect_and_track(frame)
            last_vehicles = [v for v in last_vehicles if v.confidence >= VEHICLE_MIN_CONFIDENCE]

        plate_detections: list[PlateDetection] = []
        if last_vehicles:
            for vehicle in last_vehicles:
                x1, y1, x2, y2 = vehicle.bbox
                h_car = y2 - y1
                roi = (x1, y1 + int(h_car * 0.40), x2, y2)
                plate_detections.extend(plate_det.detect(frame, vehicle_roi=roi))
        if not plate_detections:
            plate_detections = plate_det.detect(frame, vehicle_roi=None)

        plate_detections = _dedupe_boxes(plate_detections, cfg.multi_plate_max_per_frame)
        current_boxes = [d.bbox for d in plate_detections]
        all_plate_boxes_per_frame.append(current_boxes)

        if plate_detections:
            print(
                f"[pipeline] frame {frame_idx:04d}: {len(plate_detections)} plate(s)  "
                + "  ".join(f"bbox={d.bbox} conf={d.confidence:.2f}" for d in plate_detections[:2]),
                flush=True,
            )

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

        # ── OCR region candidates ──────────────────────────────────────────
        ocr_boxes = []
        if tracked_plate_box is not None:
            ocr_boxes.append(tracked_plate_box)
        for box in current_boxes:
            if tracked_plate_box is None or _iou_xywh(box, tracked_plate_box) < 0.45:
                ocr_boxes.append(box)

        for box in ocr_boxes:
            # ── Crop from ORIGINAL (unblurred) frame ──────────────────────
            crop = crop_plate(frame, box, cfg.plate_crop_margin_px)
            if crop is None:
                continue

            x, y, w, h = box
            plate_format_info = classify_plate_format(w, h)

            # Track best crop by sharpness
            sharp = _sharpness(crop)
            if sharp > best_crop_sharpness:
                best_crop_sharpness = sharp
                best_crop = crop.copy()
                best_crop_frame = frame_idx

            # Update preview crop (largest area wins)
            if last_preview_crop is None or (
                crop.shape[1] * crop.shape[0] >= last_preview_crop.shape[1] * last_preview_crop.shape[0]
            ):
                last_preview_crop = crop.copy()

            # ── OCR quality gate (relaxed thresholds) ─────────────────────
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
                # ── PASS RAW BGR CROP — no double-preprocessing ───────────
                digits, ocr_err = read_plate_crop(crop)

                print(
                    f"[pipeline] frame {frame_idx:04d} OCR box={box}  "
                    f"sharp={sharp:.1f}  raw={digits!r}  err={ocr_err}",
                    flush=True,
                )

                # Debug: save crop + log entry
                if debug_dir is not None:
                    crop_path = debug_dir / f"crop_frame_{frame_idx:04d}.jpg"
                    cv2.imwrite(str(crop_path), crop)
                    debug_log.append({
                        "frame_index": frame_idx,
                        "bbox": list(box),
                        "sharpness": round(sharp, 2),
                        "raw_ocr": digits,
                        "valid": 7 <= len(digits) <= 8,
                        "rejection_reason": ocr_err,
                    })

                if digits:
                    ocr_vote.add(digits)
                    top = ocr_vote.counter.most_common(1)
                    if top and top[0][1] >= 3:
                        selected_ocr = ocr_vote.best_valid(registry.exists) or ocr_vote.best_any()
                        print(
                            f"[pipeline] early exit — confident OCR result: {selected_ocr}",
                            flush=True,
                        )

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

        frames_out.append(out_frame)
        frames_processed += 1

    # ── Extra OCR pass on best crop if still no result ─────────────────────
    if not cfg.disable_ocr and best_crop is not None and not selected_ocr:
        print(
            f"[pipeline] running extra OCR on best crop  "
            f"frame={best_crop_frame}  sharpness={best_crop_sharpness:.1f}",
            flush=True,
        )
        # use_easyocr=True only here — keeps per-frame OCR fast
        digits, _ = read_plate_crop(best_crop, use_easyocr=True)
        print(f"[pipeline] best-crop OCR result: {digits!r}", flush=True)
        if digits:
            ocr_vote.add(digits)

        if debug_dir is not None and best_crop is not None:
            cv2.imwrite(str(debug_dir / "best_crop.jpg"), best_crop)

    # ── Finalise OCR vote ──────────────────────────────────────────────────
    if not cfg.disable_ocr and ocr_vote.counter:
        selected_ocr = ocr_vote.best_valid(registry.exists) or ocr_vote.best_any()
        validated_plate = selected_ocr  # accept even without registry match

    print(
        f"[pipeline] RESULT  frames={frames_processed}  "
        f"candidates={ocr_vote.all_candidates()}  selected={selected_ocr}",
        flush=True,
    )

    # Save debug log JSON
    if debug_dir is not None and debug_log:
        log_path = debug_dir / "ocr_log.json"
        log_path.write_text(json.dumps(debug_log, indent=2, ensure_ascii=False))
        print(f"[pipeline] debug log: {log_path}", flush=True)

    # Save best crop when debug enabled
    if debug_dir is not None and best_crop is not None:
        cv2.imwrite(str(debug_dir / "best_crop.jpg"), best_crop)

    # ── Patch plate text into already-rendered frames (no re-decode) ───────
    if selected_ocr and frames_out:
        frames_out = [
            render_privacy_frame(
                f,
                boxes,
                kernel_size=cfg.blur_kernel_size,
                preview_crop=last_preview_crop if cfg.preview_enabled else None,
                plate_text=selected_ocr,
                preview_max_w_ratio=cfg.preview_max_w_ratio,
                preview_max_h_ratio=cfg.preview_max_h_ratio,
                preview_margin_px=cfg.preview_margin_px,
                preview_zoom=cfg.preview_zoom,
            )
            for f, boxes in zip(frames_out, all_plate_boxes_per_frame)
        ]

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
            engine_version="enterprise_v3",
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
        "engine_version": "enterprise_v3",
        "multi_plate_support": True,
    }
