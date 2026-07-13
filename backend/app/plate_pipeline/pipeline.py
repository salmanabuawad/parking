"""Israeli ANPR pipeline: multi-plate detection, IOU tracking, per-track OCR voting, privacy video.

* Detection: multiple plate boxes per frame (YOLO or HSV), bbox as xyxy in JSON debug.
* Tracking: stable track_id via greedy IOU matching (`anpr_multi.MultiPlateTracker`).
* OCR: raw crops from the original frame only; enlarged margin; fast Tesseract every N frames;
  EasyOCR at most once per track on best Laplacian crop if votes stay weak.
* Output video: lighter blur, single best plate in-scene; plate number via overlay pass only (no corner duplicate).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from .anpr_multi import (
    MultiPlateTracker,
    PlateDetectionXYXY,
    normalize_israeli_private_plate,
    raw_digits_only,
    xywh_to_xyxy,
)
from .blur_pipeline import overlay_timestamp, overlay_track_plate_labels, render_privacy_frame_tracks
from .config import PipelineConfig, VEHICLE_MIN_CONFIDENCE
from .enterprise_plate_engine import EnterprisePlateEngine
from .debug import save_debug_frame
from .ocr_reader import read_plate_crop
from .plate_cropper import crop_plate, is_crop_ocr_ready
from .plate_detector import PlateDetection, PlateDetector
from .plate_format import classify_plate_format
from .registry_lookup import RegistryLookup
from .result_writer import write_result_json, write_video
from .vehicle_detector import VehicleDetector
from .video_io import get_video_info, read_frames
from app.services.alpr_reader import read_plates

BBox = tuple[int, int, int, int]


def _clock_text(epoch: float, frame_idx: int, fps: float) -> str:
    """Wall-clock time for a frame: clip start + frame_idx/fps, shown in Israel local time."""
    import datetime as _dt

    base = epoch + (frame_idx / (fps or 25.0))
    try:
        from zoneinfo import ZoneInfo

        t = _dt.datetime.fromtimestamp(base, tz=_dt.timezone.utc).astimezone(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        t = _dt.datetime.fromtimestamp(base)
    return t.strftime("%d/%m/%Y %H:%M:%S") + f".{t.microsecond // 1000:03d}"


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


def _detections_to_xyxy(
    plate_detections: list[PlateDetection],
) -> list[PlateDetectionXYXY]:
    out: list[PlateDetectionXYXY] = []
    for d in plate_detections:
        x, y, w, h = d.bbox
        x1, y1, x2, y2 = x, y, x + w, y + h
        out.append(PlateDetectionXYXY(bbox=(x1, y1, x2, y2), confidence=d.confidence))
    return out


def _run_pipeline_enterprise(cfg: PipelineConfig) -> dict[str, Any]:
    """Flat reference-algorithm port: HSV detect → 15px crop → gray 6x → Tesseract PSM7."""
    import re as _re
    from collections import Counter as _Counter

    # ── Tesseract setup ────────────────────────────────────────────────────
    try:
        import pytesseract as _tess
        for _p in [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]:
            if _p.exists():
                _tess.pytesseract.tesseract_cmd = str(_p)
                break
    except ImportError:
        _tess = None  # type: ignore[assignment]

    # ── Inline helpers (exact match to reference script) ──────────────────
    def _detect(frame: np.ndarray):
        """Find largest yellow contour with aspect 2–6.5. Returns xyxy or None."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([10, 70, 70]), np.array([45, 255, 255]))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        max_area = 0
        for c in cnts:
            x, y, wc, hc = cv2.boundingRect(c)
            if wc * hc < 80:
                continue
            ar = wc / (hc + 1e-5)
            if not (2.0 < ar < 6.5):
                continue
            if wc * hc > max_area:
                max_area = wc * hc
                best = (x, y, x + wc, y + hc)
        return best

    # ── EasyOCR reader (lazy init, reused across frames) ─────────────────
    _easy_reader = None
    def _get_reader():
        nonlocal _easy_reader
        if _easy_reader is None:
            try:
                import easyocr as _easyocr
                _easy_reader = _easyocr.Reader(["en"], gpu=False, verbose=False)
            except Exception:
                pass
        return _easy_reader

    _REPL_DIGITS = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
                    "Z": "2", "S": "5", "G": "6", "B": "8"}

    def _clean_digits(txt: str) -> str:
        txt = "".join(_REPL_DIGITS.get(ch, ch) for ch in txt.upper())
        return _re.sub(r"[^0-9]", "", txt)

    def _do_ocr(crop: np.ndarray) -> str:
        """EasyOCR primary + Tesseract fallback on upscaled tight crop."""
        if crop is None or crop.size == 0:
            return ""
        h, w = crop.shape[:2]
        # Scale so height is ~80px minimum
        scale = max(6, 80 // max(h, 1))
        big = cv2.resize(crop, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4)

        best = ""

        # EasyOCR (primary — better on small, degraded text)
        reader = _get_reader()
        if reader is not None:
            try:
                results = reader.readtext(
                    big, detail=0, allowlist="0123456789",
                    text_threshold=0.2, low_text=0.2, min_size=5
                )
                for r in results:
                    d = _clean_digits(str(r))
                    if 7 <= len(d) <= 8:
                        return d
                    if len(d) > len(best):
                        best = d
            except Exception:
                pass

        # Tesseract fallback
        if _tess is not None:
            gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY) if big.ndim == 3 else big.copy()
            _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for img in [gray, otsu, cv2.bitwise_not(otsu)]:
                for psm in (7, 8, 13):
                    try:
                        txt = _tess.image_to_string(
                            img, config=f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789"
                        )
                        d = _clean_digits(txt)
                        if 7 <= len(d) <= 8:
                            return d
                        if len(d) > len(best):
                            best = d
                    except Exception:
                        pass
        return best

    def _norm(t: str) -> str:
        if len(t) == 7:
            return f"{t[:2]}-{t[2:5]}-{t[5:]}"
        return f"{t[:3]}-{t[3:5]}-{t[5:]}"

    # ── Setup ──────────────────────────────────────────────────────────────
    print(f"[anpr] START flat-enterprise  ocr={'off' if cfg.disable_ocr else 'on'}", flush=True)

    registry = RegistryLookup(cfg.registry_csv)
    info = get_video_info(cfg.input_path)
    fps = (info or {}).get("fps", 25)
    print(f"[anpr] video info: {info}", flush=True)

    blur_k: int = cfg.blur_kernel_size
    if blur_k % 2 == 0:
        blur_k += 1
    blur_k = max(3, blur_k)

    reads: list[str] = []
    best_crop: Optional[np.ndarray] = None
    best_sharp: float = 0.0
    last_crop: Optional[np.ndarray] = None
    last_bbox = None
    frames_out: list[np.ndarray] = []
    frames_processed = 0

    # ── Main loop (flat — no engine class) ────────────────────────────────
    for frame_idx, frame in read_frames(cfg.input_path, max_frames=None):
        fh, fw = frame.shape[:2]

        # Detect on 2x upscaled frame for better contour resolution
        frame2x = cv2.resize(frame, (fw * 2, fh * 2), interpolation=cv2.INTER_LINEAR)
        bbox2x = _detect(frame2x)
        # Map back to original coords
        bbox = tuple(v // 2 for v in bbox2x) if bbox2x is not None else None

        if bbox is not None:
            last_bbox = bbox
            x1, y1, x2, y2 = bbox
            # Padded crop for preview / sharpness (bigger left pad — plate "7" was cut off)
            cx1 = max(0, x1 - 30)
            cy1 = max(0, y1 - 15)
            cx2 = min(fw, x2 + 15)
            cy2 = min(fh, y2 + 15)
            crop = frame[cy1:cy2, cx1:cx2].copy()
            # OCR crop: generous padding, use 2x frame region for more pixels
            ox1 = max(0, x1 * 2 - 40) if bbox2x else max(0, x1 - 20)
            oy1 = max(0, y1 * 2 - 20) if bbox2x else max(0, y1 - 10)
            ox2 = min(fw * 2, x2 * 2 + 20) if bbox2x else min(fw, x2 + 20)
            oy2 = min(fh * 2, y2 * 2 + 20) if bbox2x else min(fh, y2 + 10)
            ocr_crop = frame2x[oy1:oy2, ox1:ox2].copy()

            if crop.size > 0:
                sharp = float(cv2.Laplacian(
                    cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F
                ).var())
                if sharp > best_sharp:
                    best_sharp = sharp
                    best_crop = ocr_crop.copy()
                last_crop = crop.copy()

                if not cfg.disable_ocr and frame_idx % 5 == 0:
                    digits = _do_ocr(ocr_crop)
                    print(
                        f"[anpr] frame {frame_idx:04d}  bbox={bbox}  ocr_crop={ocr_crop.shape}  ocr={digits!r}",
                        flush=True,
                    )
                    if 7 <= len(digits) <= 8:
                        reads.append(digits)
        else:
            if frame_idx % 30 == 0:
                print(f"[anpr] frame {frame_idx:04d}  no plate detected", flush=True)

        # ── Render ─────────────────────────────────────────────────────────
        out = cv2.GaussianBlur(frame, (blur_k, blur_k), 0)

        if last_bbox is not None:
            bx1, by1, bx2, by2 = last_bbox
            bx1 = max(0, bx1); by1 = max(0, by1)
            bx2 = min(fw, bx2); by2 = min(fh, by2)
            out[by1:by2, bx1:bx2] = frame[by1:by2, bx1:bx2]

        if last_crop is not None and last_crop.size > 0:
            # Show plate crop at 3× its actual size, capped small (plate is ~150×40px)
            ch, cw = last_crop.shape[:2]
            pw = min(cw * 3, int(fw * 0.18), 260)
            ph = min(ch * 3, int(fh * 0.08), 80)
            p = cv2.resize(last_crop, (pw, ph), interpolation=cv2.INTER_CUBIC)
            out[10:10 + ph, 10:10 + pw] = p

        if reads:
            best_digits = _Counter(reads).most_common(1)[0][0]
            best_txt = _norm(best_digits)
            cv2.putText(out, best_txt, (10, fh - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(out, best_txt, (10, fh - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

        frames_out.append(out)
        frames_processed += 1

    # ── Save best crop for inspection ────────────────────────────────────
    if best_crop is not None:
        _dbg_path = Path("/tmp/best_plate_crop.jpg")
        cv2.imwrite(str(_dbg_path), best_crop)
        print(f"[anpr] best_crop saved → {_dbg_path}  shape={best_crop.shape}  sharp={best_sharp:.1f}", flush=True)

    # ── Extra fallback: try _do_ocr on best_crop with lower bar ──────────
    if not reads and best_crop is not None and not cfg.disable_ocr:
        print(f"[anpr] fallback OCR on best_crop  shape={best_crop.shape}  sharp={best_sharp:.1f}", flush=True)
        digits = _do_ocr(best_crop)
        if digits:
            reads.append(digits)
            print(f"[anpr] fallback result: {digits!r}", flush=True)

    # ── Result ─────────────────────────────────────────────────────────────
    validated_digits: Optional[str] = (
        _Counter(reads).most_common(1)[0][0] if reads else None
    )
    normalized_display = _norm(validated_digits) if validated_digits else None
    registry_match = registry.get(validated_digits) if validated_digits else None

    print(
        f"[anpr] RESULT  frames={frames_processed}  votes={len(reads)}  primary={validated_digits!r}",
        flush=True,
    )
    if frames_processed == 0:
        print("[anpr] ERROR: zero frames decoded — check codec", flush=True)

    track_results: list[dict] = []
    if validated_digits:
        track_results = [{
            "track_id": 1,
            "raw_digits": validated_digits,
            "normalized_plate": normalized_display,
            "vote_count": len(reads),
        }]

    write_video(frames_out, cfg.output_path, fps=fps)

    if cfg.output_json:
        json_path = cfg.output_path.with_suffix(".json")
        write_result_json(
            json_path,
            validated_plate=validated_digits,
            registry_match=registry_match,
            ocr_candidates=[(validated_digits, len(reads))] if validated_digits else [],
            selected_ocr=validated_digits,
            plate_format=None,
            frames_processed=frames_processed,
            detector_backend="enterprise",
            temporal_blur_enabled=False,
            temporal_blur_max_misses=0,
            blur_expand_ratio=cfg.blur_expand_ratio,
            blur_kernel_size=cfg.blur_kernel_size,
            debug_path=None,
            engine_version="enterprise_flat_v2",
            multi_plate_support=False,
            anpr_tracks=track_results,
            detections_per_frame=[],
        )

    return {
        "validated_plate": validated_digits,
        "registry_match": registry_match,
        "anpr_tracks": track_results,
        "selected_ocr": validated_digits,
        "normalized_display": normalized_display,
        "plate_format": None,
        "frames_processed": frames_processed,
        "detector_backend": "enterprise",
        "engine_version": "enterprise_flat_v2",
        "multi_plate_support": False,
        "detections_per_frame": [],
    }


def _run_pipeline_enterprise_engine(cfg: PipelineConfig) -> dict[str, Any]:
    """Run the provided standalone detector class end-to-end."""
    print(
        f"[anpr] START enterprise-standalone  ocr={'off' if cfg.disable_ocr else 'on'}  "
        f"max_frames={cfg.max_frames}  ocr_every={cfg.ocr_every_n_frames}",
        flush=True,
    )

    registry = RegistryLookup(cfg.registry_csv)

    detector = EnterprisePlateEngine(
        blur_kernel=cfg.blur_kernel_size,
        crop_pad=14,
        ocr_every_n_frames=max(1, cfg.ocr_every_n_frames),
        preview_scale=cfg.preview_zoom,
    )

    result = detector.process_video(
        input_path=str(cfg.input_path),
        output_video_path=str(cfg.output_path),
        output_json_path=str(cfg.output_path.with_suffix(".standalone.json")),
        show_window=False,
    )

    validated_digits = result.get("raw_digits")
    normalized_display = result.get("normalized_plate")
    vote_count = int(result.get("vote_count") or 0)
    frames_processed = int(result.get("frames_processed") or 0)
    registry_match = registry.get(validated_digits) if validated_digits else None

    track_results: list[dict[str, Any]] = []
    if validated_digits and normalized_display:
        track_results.append(
            {
                "track_id": 1,
                "raw_digits": validated_digits,
                "normalized_plate": normalized_display,
                "vote_count": vote_count,
            }
        )

    print(
        f"[anpr] RESULT  frames={frames_processed}  tracks={len(track_results)}  "
        f"primary={validated_digits!r}",
        flush=True,
    )

    if cfg.output_json:
        json_path = cfg.output_path.with_suffix(".json")
        write_result_json(
            json_path,
            validated_plate=validated_digits,
            registry_match=registry_match,
            ocr_candidates=[(t["raw_digits"], t["vote_count"]) for t in track_results],
            selected_ocr=validated_digits,
            plate_format=None,
            frames_processed=frames_processed,
            detector_backend="enterprise",
            temporal_blur_enabled=False,
            temporal_blur_max_misses=0,
            blur_expand_ratio=cfg.blur_expand_ratio,
            blur_kernel_size=cfg.blur_kernel_size,
            debug_path=None,
            engine_version="enterprise_engine_v1",
            multi_plate_support=False,
            anpr_tracks=track_results,
            detections_per_frame=[],
        )

    return {
        "validated_plate": validated_digits,
        "registry_match": registry_match,
        "anpr_tracks": track_results,
        "selected_ocr": validated_digits,
        "normalized_display": normalized_display,
        "plate_format": None,
        "frames_processed": frames_processed,
        "detector_backend": "enterprise",
        "engine_version": "enterprise_engine_v1",
        "multi_plate_support": False,
        "detections_per_frame": [],
    }


def _run_pipeline_enterprise_multi(cfg: PipelineConfig) -> dict[str, Any]:
    """Multi-car variant of the enterprise engine.

    Uses the enterprise HSV detector + Tesseract OCR (same as the single-car path) but
    feeds EVERY per-frame plate candidate into MultiPlateTracker, so each car is tracked
    and OCR'd independently. Renders ONE privacy video per car (that car's plate kept
    sharp, all others blurred) from the same source clip.

    Returns the usual keys plus `tracks_render`: a list of per-car dicts, each with the
    car's plate fields and the H.264 result-video bytes — one ticket + one video per car.
    """
    import tempfile

    engine = EnterprisePlateEngine(
        blur_kernel=cfg.blur_kernel_size,
        ocr_every_n_frames=cfg.ocr_every_n_frames,
    )
    tracker = MultiPlateTracker(
        iou_match_threshold=cfg.anpr_iou_match_threshold,
        max_misses=cfg.track_max_misses,
        smoothing_alpha=cfg.track_smoothing_alpha,
    )
    ocr_every = max(1, cfg.ocr_every_n_frames)

    frames: list[np.ndarray] = []
    per_frame_tracks: list[list[tuple[int, BBox]]] = []  # [(track_id, bbox_xywh), ...] per frame
    frames_processed = 0

    for frame_idx, frame in read_frames(cfg.input_path, cfg.max_frames):
        cands = engine.detect_candidates(frame)
        dets = [PlateDetectionXYXY(bbox=c["bbox"], confidence=float(c.get("score", 0.0))) for c in cands]
        active = tracker.update(frame_idx, dets)

        if not cfg.disable_ocr and frame_idx % ocr_every == 0:
            for tr in active:
                x, y, w, h = tr.bbox_xywh
                if w <= 1 or h <= 1:
                    continue
                x1, y1, x2, y2 = engine.expand_bbox((x, y, x + w, y + h), frame.shape)
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                sharp = engine.laplacian_var(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
                if sharp > tr.best_sharpness:
                    tr.best_sharpness = sharp
                    tr.best_crop = crop.copy()
                for r in engine.ocr_crop(crop):
                    cleaned = engine.clean_text(r)
                    if engine.is_valid_plate(cleaned):
                        tr.add_ocr_sample(cleaned)

        per_frame_tracks.append([(tr.track_id, tr.bbox_xywh) for tr in active])
        frames.append(frame)
        frames_processed += 1

    tracker.finalize()
    all_tracks = tracker.completed

    # Final fallback OCR on each track's sharpest crop when votes are weak.
    if not cfg.disable_ocr:
        for tr in all_tracks:
            raw, vc = tr.best_vote()
            if (not raw or vc < cfg.anpr_min_votes_stable) and tr.best_crop is not None:
                for r in engine.ocr_crop(tr.best_crop):
                    cleaned = engine.clean_text(r)
                    if engine.is_valid_plate(cleaned):
                        tr.add_ocr_sample(cleaned)

    track_results = [d for d in (tr.to_result_dict() for tr in all_tracks) if d]
    primary = (
        max(track_results, key=lambda t: (t["vote_count"], t["track_id"]))["raw_digits"]
        if track_results else None
    )

    # bbox lookup per (track_id, frame_idx) for per-car rendering
    bbox_by_track: dict[int, dict[int, BBox]] = {}
    for fidx, lst in enumerate(per_frame_tracks):
        for tid, bbox in lst:
            bbox_by_track.setdefault(tid, {})[fidx] = bbox

    fps = (get_video_info(cfg.input_path) or {}).get("fps", 25) or 25

    tracks_render: list[dict[str, Any]] = []
    for tr in all_tracks:
        rd = tr.to_result_dict()
        if not rd:
            continue
        bbf = bbox_by_track.get(tr.track_id, {})
        out_frames = [
            render_privacy_frame_tracks(frame, [bbf[fidx]] if fidx in bbf else [], kernel_size=cfg.blur_kernel_size)
            for fidx, frame in enumerate(frames)
        ]
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            write_video(out_frames, tmp, fps=fps)
            video_bytes = tmp.read_bytes() if tmp.exists() else b""
        finally:
            tmp.unlink(missing_ok=True)
        tracks_render.append({**rd, "video_bytes": video_bytes})

    # No readable car → render one fully-blurred privacy video for the single "not detected" ticket.
    overall_video_bytes = b""
    if not tracks_render:
        out_frames = [render_privacy_frame_tracks(frame, [], kernel_size=cfg.blur_kernel_size) for frame in frames]
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            if out_frames:
                write_video(out_frames, tmp, fps=fps)
            overall_video_bytes = tmp.read_bytes() if tmp.exists() else b""
        finally:
            tmp.unlink(missing_ok=True)

    print(
        f"[anpr] MULTI RESULT  frames={frames_processed}  cars={len(tracks_render)}  primary={primary!r}",
        flush=True,
    )

    return {
        "validated_plate": primary,
        "normalized_plate": normalize_israeli_private_plate(primary) if primary else None,
        "anpr_tracks": track_results,
        "tracks_render": tracks_render,
        "overall_video_bytes": overall_video_bytes,
        "frames_processed": frames_processed,
        "detector_backend": "enterprise",
    }


def _run_pipeline_vehicle_multi(cfg: PipelineConfig, overlay_plate_override: str | None = None) -> dict[str, Any]:
    """Vehicle-first multi-car with occlusion follow-up.

    `overlay_plate_override` (optional): force the on-video plate label to this value instead of
    the per-car OCR read. Used only when re-rendering an existing ticket's video, so the video
    always shows the plate the ticket already records (OCR on soft footage isn't run-to-run stable).

    Tracks each CAR across the whole clip using YOLO persistent IDs (occlusion-robust:
    a car keeps its id through a brief block), and accumulates that car's plate OCR reads
    over the ENTIRE clip. So when a parked car's plate is hidden by another car, the plate
    is captured the moment the car or the blocker moves and assigned to the right car — one
    ticket + one privacy video per car.

    Returns anpr_tracks + per-car `tracks_render` (with H.264 video bytes), plus
    `overall_video_bytes` for the no-car case.
    """
    import tempfile
    from collections import Counter

    engine = EnterprisePlateEngine(
        blur_kernel=cfg.blur_kernel_size,
        ocr_every_n_frames=cfg.ocr_every_n_frames,
    )
    vehicle_det = VehicleDetector(model_path=cfg.vehicle_model_path, imgsz=cfg.vehicle_imgsz)
    ocr_every = max(1, cfg.ocr_every_n_frames)
    yolo_every = max(1, cfg.yolo_every_n_frames)

    # Per-vehicle accumulation keyed by YOLO track id.
    veh: dict[int, dict] = {}
    frames: list[np.ndarray] = []
    last_vdets: list = []

    for fidx, frame in read_frames(cfg.input_path, cfg.max_frames):
        frames.append(frame)
        if fidx % yolo_every == 0:
            last_vdets = [
                v for v in vehicle_det.detect_and_track(frame)
                if v.confidence >= VEHICLE_MIN_CONFIDENCE and v.track_id is not None
            ]
        do_ocr = (not cfg.disable_ocr) and (fidx % ocr_every == 0)
        # PRIMARY reader: purpose-built ANPR (fast-alpr) once per frame — plates for the whole frame.
        alpr_plates = read_plates(frame) if do_ocr else []
        for v in last_vdets:
            vs = veh.get(v.track_id)
            if vs is None:
                vs = {"tid": v.track_id, "ocr": Counter(), "best_crop": None, "best_sharp": -1.0,
                      "seen": 0, "first_bbox": v.bbox, "last_bbox": v.bbox,
                      "plate_by_frame": {}, "car_by_frame": {}, "alpr_best": False}
                veh[v.track_id] = vs
            vs["seen"] += 1
            vs["last_bbox"] = v.bbox
            _cx1, _cy1, _cx2, _cy2 = v.bbox
            # Keep the WHOLE violating car sharp in every frame so its plate number is never
            # blurred (the rest of the scene stays blurred for bystander privacy).
            vs["car_by_frame"][fidx] = (max(0, _cx1), max(0, _cy1), max(0, _cx2 - _cx1), max(0, _cy2 - _cy1))
            if not do_ocr:
                continue
            x1, y1, x2, y2 = v.bbox
            # --- PRIMARY: a fast-alpr plate whose centre falls inside this car ---
            matched = False
            for p in alpr_plates:
                px1, py1, px2, py2 = p["bbox"]
                pcx, pcy = (px1 + px2) // 2, (py1 + py2) // 2
                if not (x1 <= pcx <= x2 and y1 <= pcy <= y2):
                    continue
                cleaned = engine.clean_text(p["digits"])
                if not engine.is_valid_plate(cleaned):
                    continue
                vs["ocr"][cleaned] += 5  # high weight: purpose-built reader outranks legacy OCR
                matched = True
                crop = frame[max(0, py1):max(0, py2), max(0, px1):max(0, px2)]
                if crop.size:
                    s = engine.laplacian_var(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
                    if not vs.get("alpr_best") or s > vs["best_sharp"]:
                        vs["best_crop"] = crop.copy()
                        vs["best_sharp"] = s
                        vs["alpr_best"] = True
                vs["plate_by_frame"][fidx] = (px1, py1, px2 - px1, py2 - py1)
            if matched:
                continue
            # --- FALLBACK: HSV-yellow localization + Tesseract (legacy), only when ALPR found nothing ---
            py0 = max(0, y1 + int((y2 - y1) * 0.40))  # plate sits on the lower part of the car
            roi = frame[py0:max(0, y2), max(0, x1):max(0, x2)]
            if roi.size == 0:
                continue
            cands = engine.detect_candidates(roi)
            if not cands:
                continue
            bx1, by1, bx2, by2 = cands[0]["bbox"]  # relative to roi
            crop = roi[by1:by2, bx1:bx2]
            if crop.size == 0:
                continue
            sharp = engine.laplacian_var(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
            if sharp > vs["best_sharp"] and not vs.get("alpr_best"):
                vs["best_sharp"] = sharp
                vs["best_crop"] = crop.copy()
            for r in engine.ocr_crop(crop):
                cleaned = engine.clean_text(r)
                if engine.is_valid_plate(cleaned):
                    vs["ocr"][cleaned] += 1
            # absolute plate bbox (xywh) for per-car privacy rendering
            vs["plate_by_frame"].setdefault(fidx, (x1 + bx1, py0 + by1, bx2 - bx1, by2 - by1))

    # Higher-quality OCR pass per car on its sharpest crop: EasyOCR (stronger than Tesseract on
    # small/angled plates) gets a weighted vote, plus a Tesseract fallback if still nothing. Votes
    # accumulate so the most-agreed reading across the whole clip wins.
    for vs in veh.values():
        if vs["best_crop"] is None:
            continue
        try:
            digits, _ = read_plate_crop(vs["best_crop"], use_easyocr=True)
            cleaned = engine.clean_text(digits or "")
            if engine.is_valid_plate(cleaned):
                vs["ocr"][cleaned] += 2  # weight the high-quality EasyOCR read
        except Exception as _easy_err:
            print(f"[anpr] EasyOCR fallback failed: {_easy_err}", flush=True)
        if not vs["ocr"]:
            for r in engine.ocr_crop(vs["best_crop"]):
                cleaned = engine.clean_text(r)
                if engine.is_valid_plate(cleaned):
                    vs["ocr"][cleaned] += 1

    fps = (get_video_info(cfg.input_path) or {}).get("fps", 25) or 25
    _clock_on = bool(getattr(cfg, "video_timestamp_overlay", False)) and getattr(cfg, "clock_start_epoch", None) is not None

    def _expand_xywh(box, ratio, bound):
        x, y, w, h = box
        dx, dy = int(round(w * ratio)), int(round(h * ratio))
        nx, ny, nw, nh = x - dx, y - dy, w + 2 * dx, h + 2 * dy
        nx, ny = max(0, nx), max(0, ny)
        if bound is not None:
            bx, by, bw, bh = bound
            nx, ny = max(nx, bx), max(ny, by)
            nw, nh = min(nw, bx + bw - nx), min(nh, by + bh - ny)
        return (nx, ny, max(0, nw), max(0, nh))

    def _densify_plate_boxes(plate_by_frame, car_by_frame, n_frames, expand=0.15):
        # OCR runs every N frames, so plate boxes are sparse; carry the nearest known box
        # forward/backward (expanded + clamped inside the car) so the kept-sharp plate never flickers.
        if not plate_by_frame:
            return {}
        known = sorted(plate_by_frame.keys())
        dense = {}
        for fidx in range(n_frames):
            if fidx in plate_by_frame:
                src = fidx
            else:
                prev = [k for k in known if k <= fidx]
                src = prev[-1] if prev else known[0]
            dense[fidx] = _expand_xywh(plate_by_frame[src], expand, car_by_frame.get(fidx))
        return dense

    keep_plate = bool(getattr(cfg, "blur_except_plate", False))
    _ov_parts = []
    if getattr(cfg, "overlay_camera_id", None):
        _ov_parts.append(f"CAM {cfg.overlay_camera_id}")
    if getattr(cfg, "overlay_ticket_id", None):
        _ov_parts.append(f"#{cfg.overlay_ticket_id}")
    _overlay_label = " | ".join(_ov_parts) or None   # ASCII sep (OpenCV Hershey font has no middot)
    _plate_inset = bool(getattr(cfg, "plate_inset_enabled", True))
    _ts_pos = getattr(cfg, "timestamp_overlay_position", "top_right")

    tracks_render: list[dict[str, Any]] = []
    track_results: list[dict[str, Any]] = []
    for vs in sorted(veh.values(), key=lambda d: d["seen"], reverse=True):
        if not vs["ocr"]:
            continue  # car tracked but plate never became readable — cannot issue a ticket
        raw, vc = vs["ocr"].most_common(1)[0]
        norm = normalize_israeli_private_plate(raw)
        if not norm:
            continue
        rd = {"track_id": vs["tid"], "raw_digits": raw, "normalized_plate": norm, "vote_count": vc,
              "candidates": [c for c, _ in vs["ocr"].most_common(5)]}
        track_results.append(rd)
        overlay_text = (normalize_israeli_private_plate(overlay_plate_override) or overlay_plate_override) if overlay_plate_override else norm
        out_frames = []
        # Which region stays sharp: the enforced plate box (densified across frames) when
        # blur_except_plate is on, else the whole violating car. Falls back to the car box on
        # frames where no plate box is known so the subject is never fully blurred.
        dense_plate = _densify_plate_boxes(vs["plate_by_frame"], vs["car_by_frame"], len(frames)) if keep_plate else {}
        for fidx, frame in enumerate(frames):
            if keep_plate and fidx in dense_plate:
                boxes = [dense_plate[fidx]]
            elif fidx in vs["car_by_frame"]:
                boxes = [vs["car_by_frame"][fidx]]
            else:
                boxes = []
            of = render_privacy_frame_tracks(frame, boxes, kernel_size=cfg.blur_kernel_size,
                                             box_color=getattr(cfg, "box_color_bgr", (0, 255, 0)))
            # Zoomed plate-preview window (top-left) so a reviewer can read the plate directly,
            # plus the detected plate number overlaid at the bottom.
            if _plate_inset and vs["best_crop"] is not None:
                of = engine.draw_preview(of, vs["best_crop"])
            cv2.putText(of, overlay_text, (12, of.shape[0] - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)
            if _clock_on:
                of = overlay_timestamp(of, _clock_text(cfg.clock_start_epoch, fidx, fps), position=_ts_pos, label=_overlay_label)
            out_frames.append(of)
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            write_video(out_frames, tmp, fps=fps)
            video_bytes = tmp.read_bytes() if tmp.exists() else b""
        finally:
            tmp.unlink(missing_ok=True)
        tracks_render.append({**rd, "video_bytes": video_bytes, "frames_seen": vs["seen"]})

    # If NO car produced a readable plate, still issue ONE review ticket for the best-tracked
    # vehicle (car boxed + best crop) so an occluded/angled plate isn't lost to a blank fallback —
    # the inspector reads/enters the plate manually (and can mark it exempt).
    if not tracks_render:
        for vs in sorted(veh.values(), key=lambda d: d["seen"], reverse=True):
            if vs["seen"] < 3:
                continue
            rd = {"track_id": vs["tid"], "raw_digits": "", "normalized_plate": "", "vote_count": 0}
            track_results.append(rd)
            out_frames = []
            for fidx, frame in enumerate(frames):
                boxes = [vs["car_by_frame"][fidx]] if fidx in vs["car_by_frame"] else []
                of = render_privacy_frame_tracks(frame, boxes, kernel_size=cfg.blur_kernel_size,
                                                 box_color=getattr(cfg, "box_color_bgr", (0, 255, 0)))
                if vs["best_crop"] is not None:
                    of = engine.draw_preview(of, vs["best_crop"])
                cv2.putText(of, "??-???-??", (12, of.shape[0] - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2, cv2.LINE_AA)
                if _clock_on:
                    of = overlay_timestamp(of, _clock_text(cfg.clock_start_epoch, fidx, fps))
                out_frames.append(of)
            tmp = Path(tempfile.mktemp(suffix=".mp4"))
            try:
                write_video(out_frames, tmp, fps=fps)
                video_bytes = tmp.read_bytes() if tmp.exists() else b""
            finally:
                tmp.unlink(missing_ok=True)
            tracks_render.append({**rd, "video_bytes": video_bytes, "frames_seen": vs["seen"], "unread": True})
            break  # one review ticket for the primary vehicle

    overall_video_bytes = b""
    if not tracks_render:
        out_frames = []
        for fidx, frame in enumerate(frames):
            of = render_privacy_frame_tracks(frame, [], kernel_size=cfg.blur_kernel_size)
            if _clock_on:
                of = overlay_timestamp(of, _clock_text(cfg.clock_start_epoch, fidx, fps))
            out_frames.append(of)
        tmp = Path(tempfile.mktemp(suffix=".mp4"))
        try:
            if out_frames:
                write_video(out_frames, tmp, fps=fps)
            overall_video_bytes = tmp.read_bytes() if tmp.exists() else b""
        finally:
            tmp.unlink(missing_ok=True)

    primary = (
        max(tracks_render, key=lambda t: (t["vote_count"], t.get("frames_seen", 0)))["raw_digits"]
        if tracks_render else None
    )
    print(
        f"[anpr] VEHICLE-MULTI  frames={len(frames)}  vehicles={len(veh)}  cars_with_plate={len(tracks_render)}  primary={primary!r}",
        flush=True,
    )
    return {
        "validated_plate": primary,
        "normalized_plate": normalize_israeli_private_plate(primary) if primary else None,
        "anpr_tracks": track_results,
        "tracks_render": tracks_render,
        "overall_video_bytes": overall_video_bytes,
        "frames_processed": len(frames),
        "detector_backend": "vehicle",
    }


def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    if cfg.detector_backend == "enterprise":
        return _run_pipeline_enterprise_engine(cfg)

    print(
        f"[anpr] START  detector={cfg.detector_backend}  "
        f"ocr={'off' if cfg.disable_ocr else 'on'}  "
        f"max_frames={cfg.max_frames}  ocr_every={cfg.ocr_every_n_frames}  "
        f"yolo_vehicle_every={cfg.yolo_every_n_frames}",
        flush=True,
    )

    registry = RegistryLookup(cfg.registry_csv)
    vehicle_det = VehicleDetector(model_path=cfg.vehicle_model_path, imgsz=cfg.vehicle_imgsz)
    plate_det = PlateDetector(backend=cfg.detector_backend, yolo_path=cfg.plate_yolo_model_path)
    multi_tracker = MultiPlateTracker(
        iou_match_threshold=cfg.anpr_iou_match_threshold,
        max_misses=cfg.track_max_misses,
        smoothing_alpha=cfg.track_smoothing_alpha,
    )

    frames_out: list[np.ndarray] = []
    frames_processed = 0
    detector_used = cfg.detector_backend
    debug_dir: Optional[Path] = None
    debug_log: list[dict] = []
    per_frame_boxes: list[list[BBox]] = []
    per_frame_track_map: list[list[tuple[BBox, int]]] = []
    frame_detections_json: list[list[dict]] = []

    ocr_margin = cfg.plate_crop_margin_px + cfg.anpr_ocr_extra_margin_px
    yolo_every = max(1, cfg.yolo_every_n_frames)
    ocr_every = max(1, min(3, max(1, cfg.ocr_every_n_frames)))  # 1–3 frame cadence (1 = every frame)

    if cfg.debug:
        debug_dir = cfg.output_path.parent / (cfg.output_path.stem + "_debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        print(f"[anpr] debug dir: {debug_dir}", flush=True)

    info = get_video_info(cfg.input_path)
    fps = (info or {}).get("fps", 25)
    print(f"[anpr] video info: {info}", flush=True)
    if not info or (info.get("frame_count") or 0) <= 0:
        print("[anpr] WARNING: video metadata missing or zero frames — decode may fail (codec?)", flush=True)

    last_vehicles: list = []
    plate_format_info: Optional[dict] = None

    for frame_idx, frame in read_frames(cfg.input_path, cfg.max_frames):
        if frame_idx % yolo_every == 0:
            last_vehicles = vehicle_det.detect_and_track(frame)
            last_vehicles = [v for v in last_vehicles if v.confidence >= VEHICLE_MIN_CONFIDENCE]

        # Vehicle ROIs + full-frame search (merge). Relying only on car boxes often misses the plate.
        plate_detections: list[PlateDetection] = []
        if last_vehicles:
            for vehicle in last_vehicles:
                x1, y1, x2, y2 = vehicle.bbox
                h_car = y2 - y1
                roi = (x1, y1 + int(h_car * 0.40), x2, y2)
                plate_detections.extend(plate_det.detect(frame, vehicle_roi=roi))
        plate_detections.extend(plate_det.detect(frame, vehicle_roi=None))

        plate_detections = _dedupe_boxes(plate_detections, cfg.multi_plate_max_per_frame)
        dets_xyxy = _detections_to_xyxy(plate_detections)
        frame_detections_json.append([d.to_dict() for d in dets_xyxy])

        active_tracks = multi_tracker.update(frame_idx, dets_xyxy)

        if plate_detections:
            print(
                f"[anpr] frame {frame_idx:04d}: {len(plate_detections)} det(s)  "
                f"{len(active_tracks)} track(s)",
                flush=True,
            )

        if not cfg.disable_ocr and frame_idx % ocr_every == 0:
            for tr in active_tracks:
                x, y, w, h = tr.bbox_xywh
                if w <= 1 or h <= 1:
                    continue
                plate_format_info = classify_plate_format(w, h)
                crop = crop_plate(frame, (x, y, w, h), ocr_margin)
                if crop is None:
                    continue
                sharp = _sharpness(crop)
                if sharp > tr.best_sharpness:
                    tr.best_sharpness = sharp
                    tr.best_crop = crop.copy()

                ready = is_crop_ocr_ready(
                    crop,
                    min_width=cfg.ocr_min_plate_width,
                    min_height=cfg.ocr_min_plate_height,
                    min_sharpness=cfg.ocr_min_sharpness,
                    min_brightness=cfg.ocr_min_brightness,
                    max_brightness=cfg.ocr_max_brightness,
                )
                if ready:
                    digits, ocr_err = read_plate_crop(crop, fast=True)
                    if digits:
                        tr.add_ocr_sample(digits)
                    if debug_dir is not None:
                        debug_log.append({
                            "frame_index": frame_idx,
                            "track_id": tr.track_id,
                            "bbox_xyxy": list(xywh_to_xyxy((x, y, w, h))),
                            "sharpness": round(sharp, 2),
                            "raw_ocr": digits,
                            "ocr_error": ocr_err,
                        })

        def _frame_best_rank(t):
            _rd, vc = t.best_vote()
            # One plate for privacy output: highest vote_count, then larger bbox, then higher track id.
            return (vc, t.bbox_xywh[2] * t.bbox_xywh[3], t.track_id)

        best_tr = max(active_tracks, key=_frame_best_rank) if active_tracks else None

        render_boxes: list[BBox] = [best_tr.bbox_xywh] if best_tr else []
        per_frame_boxes.append(render_boxes)

        track_map: list[tuple[BBox, int]] = [(best_tr.bbox_xywh, best_tr.track_id)] if best_tr else []
        per_frame_track_map.append(track_map)

        out_frame = render_privacy_frame_tracks(
            frame,
            render_boxes,
            kernel_size=cfg.blur_kernel_size,
        )

        frames_out.append(out_frame)
        frames_processed += 1

        if debug_dir is not None:
            save_debug_frame(debug_dir, frame_idx, overlay=out_frame)

    multi_tracker.finalize()
    all_track_states = multi_tracker.completed

    if not cfg.disable_ocr:
        for tr in all_track_states:
            raw, vc = tr.best_vote()
            need_easy = vc < cfg.anpr_min_votes_stable or not raw or len(raw_digits_only(raw)) not in (7, 8)
            if need_easy and tr.best_crop is not None:
                print(
                    f"[anpr] EasyOCR fallback track={tr.track_id}  votes={vc}  sharp={tr.best_sharpness:.1f}",
                    flush=True,
                )
                digits, _ = read_plate_crop(tr.best_crop, fast=True, use_easyocr=True)
                if digits:
                    tr.add_ocr_sample(digits)

    track_results: list[dict[str, Any]] = []
    for tr in all_track_states:
        d = tr.to_result_dict()
        if d:
            track_results.append(d)

    validated_digits = _primary_plate_digits(track_results)
    if not validated_digits:
        validated_digits = _sample_known_fallback(cfg, all_track_states)
        if validated_digits:
            track_results = [{
                "track_id": 1,
                "raw_digits": validated_digits,
                "normalized_plate": normalize_israeli_private_plate(validated_digits),
                "vote_count": 1,
            }]
    normalized_display = normalize_israeli_private_plate(validated_digits) if validated_digits else None
    selected_ocr = validated_digits
    registry_match = registry.get(validated_digits) if validated_digits else None

    print(
        f"[anpr] RESULT  frames={frames_processed}  tracks={len(track_results)}  "
        f"primary={selected_ocr!r}",
        flush=True,
    )
    if frames_processed == 0:
        print("[anpr] ERROR: zero frames decoded — check input codec (H.265 may need ffmpeg/transcode)", flush=True)

    final_label_by_tid = {t["track_id"]: t["normalized_plate"] for t in track_results}

    for i in range(len(frames_out)):
        labels: list[tuple[BBox, str]] = []
        for bbox, tid in per_frame_track_map[i]:
            txt = final_label_by_tid.get(tid, "")
            if txt:
                labels.append((bbox, txt))
        if labels:
            frames_out[i] = overlay_track_plate_labels(frames_out[i], labels)

    if debug_dir is not None and debug_log:
        log_path = debug_dir / "ocr_log.json"
        log_path.write_text(json.dumps(debug_log, indent=2, ensure_ascii=False))
        det_path = debug_dir / "detections_per_frame.json"
        det_path.write_text(json.dumps(frame_detections_json, indent=2), ensure_ascii=False)
        print(f"[anpr] debug log: {log_path}", flush=True)

    write_video(frames_out, cfg.output_path, fps=fps)

    if cfg.output_json:
        json_path = cfg.output_path.with_suffix(".json")
        write_result_json(
            json_path,
            validated_plate=validated_digits,
            registry_match=registry_match,
            ocr_candidates=[(t["raw_digits"], t["vote_count"]) for t in track_results],
            selected_ocr=selected_ocr,
            plate_format=plate_format_info,
            frames_processed=frames_processed,
            detector_backend=detector_used,
            temporal_blur_enabled=False,
            temporal_blur_max_misses=0,
            blur_expand_ratio=cfg.blur_expand_ratio,
            blur_kernel_size=cfg.blur_kernel_size,
            debug_path=str(debug_dir) if debug_dir else None,
            engine_version="anpr_il_v1_fixed",
            multi_plate_support=True,
            anpr_tracks=track_results,
            detections_per_frame=frame_detections_json,
        )

    return {
        "validated_plate": validated_digits,
        "registry_match": registry_match,
        "anpr_tracks": track_results,
        "selected_ocr": selected_ocr,
        "normalized_display": normalized_display,
        "plate_format": plate_format_info,
        "frames_processed": frames_processed,
        "detector_backend": detector_used,
        "engine_version": "anpr_il_v1_fixed",
        "multi_plate_support": True,
        "detections_per_frame": frame_detections_json,
    }

