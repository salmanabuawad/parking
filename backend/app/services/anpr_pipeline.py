"""ANPR pipeline: YOLO vehicle tracking → YOLO/HSV plate detection → EasyOCR.

Adapted from user-provided ANPRPipeline code (originally used PaddleOCR).
Uses EasyOCR as the OCR backend (better Windows compatibility).

Exposes two public functions:
  - extract_plate_from_bytes(video_bytes) → (plate_text, error)
  - detect_plate_in_frame(frame, vehicle_roi) → Optional[BBox]  (xywh)
"""

from __future__ import annotations

import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

BBox = Tuple[int, int, int, int]  # x, y, w, h (OpenCV convention)

# ─── EasyOCR singleton ───────────────────────────────────────────────────────

_ocr_reader = None
_ocr_failed = False


def _get_ocr():
    global _ocr_reader, _ocr_failed
    if _ocr_failed:
        return None
    if _ocr_reader is not None:
        return _ocr_reader
    try:
        import easyocr  # type: ignore
        # gpu=False → CPU inference; model downloads on first use
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        print("[ANPR] EasyOCR loaded", flush=True)
        return _ocr_reader
    except Exception as e:
        _ocr_failed = True
        print(f"[ANPR] EasyOCR not available ({e}); will use Tesseract fallback", flush=True)
        return None


def is_paddle_available() -> bool:
    """Backwards-compat name — returns True when EasyOCR is available."""
    return _get_ocr() is not None


# ─── Plate enhancement & OCR ─────────────────────────────────────────────────

def _enhance_plate(crop: np.ndarray, scale: int = 4) -> np.ndarray:
    """Upscale and enhance a plate crop for OCR."""
    if crop.size == 0:
        return crop
    up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY) if up.ndim == 3 else up
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    return clahe.apply(gray)  # EasyOCR accepts grayscale


def _normalize_text(text: str) -> str:
    return re.sub(r"[^0-9]", "", text)


def read_plate_crop(crop: np.ndarray) -> tuple[str, float]:
    """Run EasyOCR on a plate crop.

    Tries multiple preprocessing variants; returns the reading with the most
    digits (7-8 preferred) and highest confidence.
    Returns (digits_only, confidence).
    """
    reader = _get_ocr()
    if reader is None or crop.size == 0:
        return "", 0.0
    try:
        enhanced = _enhance_plate(crop)
        # Also try inverted (black on white) for some plate styles
        inverted = cv2.bitwise_not(enhanced)

        best_text = ""
        best_conf = 0.0

        for variant in (enhanced, inverted):
            results = reader.readtext(variant, detail=1)
            # Collect all digit sequences from all bounding boxes
            all_digits = "".join(_normalize_text(txt) for _, txt, _ in results)
            confs = [float(c) for _, _, c in results if c > 0]
            avg_conf = sum(confs) / len(confs) if confs else 0.0

            if all_digits and (
                len(all_digits) > len(best_text)
                or (len(all_digits) == len(best_text) and avg_conf > best_conf)
            ):
                best_text = all_digits
                best_conf = avg_conf

        return best_text, best_conf
    except Exception:
        return "", 0.0


# ─── YOLO vehicle tracker ────────────────────────────────────────────────────

_VEHICLE_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, truck
_vehicle_model = None
_vehicle_failed = False


def _get_vehicle_model(model_path: str = "yolov8n.pt"):
    global _vehicle_model, _vehicle_failed
    if _vehicle_failed:
        return None
    if _vehicle_model is not None:
        return _vehicle_model
    try:
        from ultralytics import YOLO  # type: ignore
        _vehicle_model = YOLO(model_path)
        print("[ANPR] YOLO vehicle model loaded", flush=True)
        return _vehicle_model
    except Exception as e:
        _vehicle_failed = True
        print(f"[ANPR] YOLO vehicle model not available ({e})", flush=True)
        return None


def detect_and_track_vehicles(frame: np.ndarray) -> list[dict]:
    """Detect + track vehicles. Returns list of {track_id, bbox:(x1,y1,x2,y2), conf}."""
    model = _get_vehicle_model()
    if model is None:
        return []
    try:
        results = model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.25,
            iou=0.5,
            verbose=False,
        )
        if not results:
            return []
        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None or boxes.xyxy is None:
            return []

        xyxy = boxes.xyxy.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.zeros(len(xyxy))
        clss = boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else np.zeros(len(xyxy), dtype=int)
        ids = boxes.id
        ids = ids.cpu().numpy().astype(int) if ids is not None else np.arange(len(xyxy))

        out = []
        for box, conf, cls_id, tid in zip(xyxy, confs, clss, ids):
            if int(cls_id) not in _VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = map(int, box.tolist())
            out.append({"track_id": int(tid), "bbox": (x1, y1, x2, y2), "conf": float(conf)})
        return out
    except Exception:
        return []


# ─── YOLO plate detector ─────────────────────────────────────────────────────

_plate_model = None
_plate_failed = True  # disabled until a model path is configured


def configure_plate_model(model_path: str) -> bool:
    """Load a YOLO plate detection model. Returns True on success."""
    global _plate_model, _plate_failed
    try:
        from ultralytics import YOLO  # type: ignore
        p = Path(model_path)
        if not p.exists():
            return False
        _plate_model = YOLO(str(p))
        _plate_failed = False
        print(f"[ANPR] YOLO plate model loaded: {p}", flush=True)
        return True
    except Exception as e:
        _plate_failed = True
        print(f"[ANPR] YOLO plate model failed ({e})", flush=True)
        return False


def _detect_plate_yolo(frame: np.ndarray, roi_xyxy: Optional[tuple] = None) -> Optional[BBox]:
    """Detect plate with YOLO. roi_xyxy is (x1,y1,x2,y2). Returns xywh or None."""
    if _plate_failed or _plate_model is None:
        return None
    h, w = frame.shape[:2]
    crop = frame
    ox = oy = 0
    if roi_xyxy:
        rx1, ry1, rx2, ry2 = roi_xyxy
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(w, rx2), min(h, ry2)
        crop = frame[ry1:ry2, rx1:rx2]
        ox, oy = rx1, ry1
    if crop.size == 0:
        return None
    try:
        results = _plate_model.predict(crop, conf=0.20, iou=0.4, verbose=False)
        if not results:
            return None
        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None or boxes.xyxy is None or len(boxes.xyxy) == 0:
            return None
        xyxy = boxes.xyxy.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy()
        best = int(np.argmax(confs))
        x1, y1, x2, y2 = xyxy[best]
        return (ox + int(x1), oy + int(y1), int(x2 - x1), int(y2 - y1))
    except Exception:
        return None


def _detect_plate_hsv(frame: np.ndarray, roi_xyxy: Optional[tuple] = None) -> Optional[BBox]:
    """Detect plate with HSV color filtering. Returns xywh or None."""
    h_frame, w_frame = frame.shape[:2]
    region = frame
    ox = oy = 0
    if roi_xyxy:
        rx1, ry1, rx2, ry2 = roi_xyxy
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(w_frame, rx2), min(h_frame, ry2)
        region = frame[ry1:ry2, rx1:rx2]
        ox, oy = rx1, ry1
    if region.size == 0:
        return None

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array([15, 80, 100], np.uint8), np.array([38, 255, 255], np.uint8))
    white = cv2.inRange(hsv, np.array([0, 0, 140], np.uint8), np.array([180, 60, 255], np.uint8))
    mask = cv2.bitwise_or(yellow, white)

    # Smaller kernels: 3×3 OPEN, 7×7 CLOSE (test engine values)
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k2)

    gray_r = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_reg, w_reg = region.shape[:2]
    best = None
    best_score = -1e9
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if bw < 40 or bh < 12:
            continue
        ratio = bw / float(bh) if bh > 0 else 0
        if not (2.5 <= ratio <= 7.0):
            continue
        # Edge density (filter out sand/flat regions)
        roi_e = cv2.Canny(gray_r[y:y+bh, x:x+bw], 80, 200)
        edge_density = float(roi_e.mean() / 255.0)
        cx = x + bw / 2.0
        cy = y + bh / 2.0
        pos_score = (
            (1.0 - abs(cx - w_reg * 0.5) / max(w_reg * 0.5, 1)) * 0.6
            + (1.0 - abs(cy - h_reg * 0.6) / max(h_reg * 0.6, 1)) * 0.4
        )
        score = area * 0.01 + edge_density * 40.0 + pos_score * 10.0
        if score > best_score:
            best_score = score
            best = (ox + x, oy + y, bw, bh)
    return best


def detect_plate_in_frame(
    frame: np.ndarray,
    vehicle_roi_xyxy: Optional[tuple] = None,
) -> Optional[BBox]:
    """Detect license plate: YOLO first, HSV fallback. Returns xywh or None."""
    box = _detect_plate_yolo(frame, vehicle_roi_xyxy)
    if box is None:
        box = _detect_plate_hsv(frame, vehicle_roi_xyxy)
    return box


# ─── Per-track state ─────────────────────────────────────────────────────────

@dataclass
class _TrackState:
    track_id: int
    best_digits: Optional[str] = None
    best_score: float = 0.0
    missing_frames: int = 0


# ─── Main extraction function ─────────────────────────────────────────────────

def extract_plate_from_bytes(video_bytes: bytes) -> tuple[str, Optional[str]]:
    """
    Full ANPR pipeline on video bytes.

    1. YOLO vehicle tracking per frame (when vehicle model available)
    2. Within vehicle lower-ROI: YOLO/HSV plate detection
    3. EasyOCR on plate crop
    4. Majority vote across all frames

    Returns (plate_digits, error_message).
    plate_digits is "11111" when nothing valid was found.
    """
    if not video_bytes:
        return "11111", "No video bytes"

    # Ensure EasyOCR is available before processing
    if _get_ocr() is None:
        return "11111", "EasyOCR not available"

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        tmp_path = f.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return "11111", "Could not open video"

        tracks: Dict[int, _TrackState] = {}
        ocr_votes: Counter = Counter()
        frame_idx = 0
        ocr_every = 3          # run OCR every N frames
        max_missing = 45       # frames before a track is expired
        min_ocr_conf = 0.01    # EasyOCR gives low scores on small plates; vote handles noise

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            h_frame, w_frame = frame.shape[:2]
            vehicles = detect_and_track_vehicles(frame)

            # ── No vehicle detector → full-frame plate search ──
            if not vehicles:
                if frame_idx % ocr_every == 0:
                    box = detect_plate_in_frame(frame)
                    if box:
                        crop = _crop_xywh(frame, box)
                        if crop is not None and crop.size > 0:
                            digits, conf = read_plate_crop(crop)
                            if digits and conf >= min_ocr_conf and 7 <= len(digits) <= 8:
                                ocr_votes[digits] += 1
                frame_idx += 1
                continue

            # ── Per-vehicle processing ──
            active_ids = set()
            for det in vehicles:
                tid = det["track_id"]
                vx1, vy1, vx2, vy2 = det["bbox"]
                vx1, vy1 = max(0, vx1), max(0, vy1)
                vx2, vy2 = min(w_frame, vx2), min(h_frame, vy2)
                active_ids.add(tid)

                if tid not in tracks:
                    tracks[tid] = _TrackState(track_id=tid)
                track = tracks[tid]
                track.missing_frames = 0

                if frame_idx % ocr_every == 0:
                    # Plates are on the lower 60% of a vehicle
                    h_car = vy2 - vy1
                    plate_roi = (vx1, vy1 + int(h_car * 0.40), vx2, vy2)
                    box = detect_plate_in_frame(frame, plate_roi)
                    if box:
                        crop = _crop_xywh(frame, box)
                        if crop is not None and crop.size > 0:
                            digits, conf = read_plate_crop(crop)
                            if digits and conf >= min_ocr_conf and 7 <= len(digits) <= 8:
                                sharp = _sharpness(crop)
                                score = conf * (1.0 + min(sharp, 500.0) / 1000.0)
                                if score > track.best_score:
                                    track.best_digits = digits
                                    track.best_score = score
                                ocr_votes[digits] += 1

            # Expire lost tracks
            for tid in list(tracks.keys()):
                if tid not in active_ids:
                    tracks[tid].missing_frames += 1
                    if tracks[tid].missing_frames > max_missing:
                        del tracks[tid]

            frame_idx += 1

        cap.release()

        if not ocr_votes:
            return "11111", "EasyOCR: no valid plate readings"

        best, count = ocr_votes.most_common(1)[0]
        total = sum(ocr_votes.values())

        # Position-consensus when all votes are tied at 1
        if count == 1 and total >= 3:
            candidates = [p for p in ocr_votes if 7 <= len(p) <= 8]
            if candidates:
                common_len = Counter(len(p) for p in candidates).most_common(1)[0][0]
                same_len = [p for p in candidates if len(p) == common_len]
                if same_len:
                    consensus = "".join(
                        Counter(p[i] for p in same_len).most_common(1)[0][0]
                        for i in range(common_len)
                    )
                    print(f"[ANPR] Position consensus: {consensus}", flush=True)
                    best = consensus

        print(f"[ANPR] Votes: {dict(ocr_votes.most_common(5))} → {best} ({count}/{total})", flush=True)
        return best, None

    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _crop_xywh(frame: np.ndarray, box: BBox) -> Optional[np.ndarray]:
    x, y, w, h = box
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2]


def _sharpness(img: np.ndarray) -> float:
    if img.size == 0:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


# ─── Auto-load plate model if available ──────────────────────────────────────

def _auto_load_plate_model() -> None:
    candidates = [
        "models/license_plate_detector.pt",
        "yolo_plate.pt",
        "plate_detector.pt",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            configure_plate_model(str(p))
            return


_auto_load_plate_model()
