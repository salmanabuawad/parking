"""Video processing for review mode.

Behavior requested:
- detect plate first
- keep the plate area sharp
- blur everything else
- keep the plate visible across short detection misses using temporal tracking

This file preserves the main public API used by the repo:
- extract_video_params(...)
- detect_plate_box(...)
- extract_license_plate(...)
- process_video(...)
- process_video_fast_hsv(...)
- process_video_with_violation_pipeline(...)
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import pytesseract

    _TESSERACT_PATHS = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for _p in _TESSERACT_PATHS:
        if _p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(_p)
            break
except ImportError:
    pytesseract = None

HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)
HSV_LOWER_LIGHT = (15, 30, 150)
HSV_UPPER_LIGHT = (40, 255, 255)

PLATE_MIN_RATIO = 1.5
PLATE_MAX_RATIO = 7.0
MIN_PLATE_AREA = 200
BLUR_KERNEL = 15
MAX_PLATE_AREA_RATIO = 0.12

MAX_TRACK_MISSES = 8
SMOOTHING_ALPHA = 0.65

PLATE_FORMAT_PRESETS = [
    {"name": "private_long", "ratio": 52 / 12, "width_cm": 52.0, "height_cm": 12.0},
    {"name": "private_rect", "ratio": 32 / 16, "width_cm": 32.0, "height_cm": 16.0},
    {"name": "motorcycle", "ratio": 17 / 16, "width_cm": 17.0, "height_cm": 16.0},
    {"name": "scooter", "ratio": 17 / 12, "width_cm": 17.0, "height_cm": 12.0},
]


def classify_plate_format(box_w: int, box_h: int) -> Optional[dict]:
    if box_h <= 0:
        return None
    ratio = box_w / box_h
    return min(PLATE_FORMAT_PRESETS, key=lambda p: abs(p["ratio"] - ratio))


@dataclass
class PlateTracker:
    max_misses: int = MAX_TRACK_MISSES
    alpha: float = SMOOTHING_ALPHA

    def __post_init__(self) -> None:
        self.last_box: Optional[Tuple[int, int, int, int]] = None
        self.miss_count = 0

    def update(self, box: Optional[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
        if box is not None:
            self.miss_count = 0
            if self.last_box is None:
                self.last_box = box
                return box
            x = int(self.alpha * box[0] + (1 - self.alpha) * self.last_box[0])
            y = int(self.alpha * box[1] + (1 - self.alpha) * self.last_box[1])
            w = int(self.alpha * box[2] + (1 - self.alpha) * self.last_box[2])
            h = int(self.alpha * box[3] + (1 - self.alpha) * self.last_box[3])
            self.last_box = (x, y, w, h)
            return self.last_box

        self.miss_count += 1
        if self.miss_count > self.max_misses:
            self.last_box = None
            return None
        return self.last_box


def _normalize_blur_kernel(blur_strength: int = 0) -> int:
    k = int(blur_strength or BLUR_KERNEL)
    if k < 3:
        k = BLUR_KERNEL
    if k % 2 == 0:
        k += 1
    return k


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        raise RuntimeError("No ffmpeg found. Install imageio-ffmpeg or add ffmpeg to PATH.")


def _get_ffprobe() -> Optional[str]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    try:
        ffmpeg = _get_ffmpeg()
        base = Path(ffmpeg).parent
        for name in ("ffprobe", "ffprobe.exe"):
            p = base / name
            if p.exists():
                return str(p)
    except RuntimeError:
        pass
    return None


def _parse_iso6709_location(s: str) -> Optional[dict]:
    if not s or not isinstance(s, str):
        return None
    s = s.strip().rstrip("/")
    m = re.match(r"([+-]?\d+(?:\.\d+)?)([+-]?\d+(?:\.\d+)?)$", s)
    if m:
        try:
            lat = float(m.group(1))
            lon = float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return {"latitude": lat, "longitude": lon}
        except ValueError:
            pass
    return None


def extract_video_params(input_path: str) -> dict:
    out: dict[str, Any] = {}
    ffprobe = _get_ffprobe()
    if not ffprobe:
        return out
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_format", "-show_streams", "-print_format", "json", input_path],
            capture_output=True,
            timeout=15,
            text=True,
        )
        if result.returncode != 0 or not result.stdout:
            return out
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug("extract_video_params failed: %s", e)
        return out

    fmt = data.get("format") or {}
    if fmt.get("duration"):
        try:
            out["duration_sec"] = round(float(fmt["duration"]), 2)
        except (TypeError, ValueError):
            pass
    if fmt.get("size"):
        try:
            out["size_bytes"] = int(fmt["size"])
        except (TypeError, ValueError):
            pass
    if fmt.get("bit_rate") and fmt["bit_rate"] != "N/A":
        try:
            out["bit_rate"] = int(fmt["bit_rate"])
        except (TypeError, ValueError):
            pass

    tags = fmt.get("tags") or {}
    for key in ("location", "location-eng", "com.apple.quicktime.location.ISO6709"):
        val = tags.get(key)
        if val and isinstance(val, str):
            parsed = _parse_iso6709_location(val)
            if parsed:
                out["gps_from_video"] = parsed
                break

    if "gps_from_video" not in out:
        for k, val in tags.items():
            if "location" in k.lower() and val and isinstance(val, str):
                parsed = _parse_iso6709_location(val)
                if parsed:
                    out["gps_from_video"] = parsed
                    break

    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video":
            if stream.get("width") is not None:
                try:
                    out["width"] = int(stream["width"])
                except (TypeError, ValueError):
                    pass
            if stream.get("height") is not None:
                try:
                    out["height"] = int(stream["height"])
                except (TypeError, ValueError):
                    pass
            if stream.get("codec_name"):
                out["codec"] = str(stream["codec_name"])
            if stream.get("r_frame_rate"):
                out["r_frame_rate"] = str(stream["r_frame_rate"])
            if stream.get("nb_frames"):
                try:
                    out["nb_frames"] = int(stream["nb_frames"])
                except (TypeError, ValueError):
                    pass
            break
    return out


def _process_ffmpeg_only(input_path: str, blur: int = 0) -> bytes:
    ffmpeg = _get_ffmpeg()
    out_path = tempfile.mktemp(suffix="_h264.mp4")
    try:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            out_path,
        ]
        if blur > 0:
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                input_path,
                "-vf",
                f"boxblur=lr={blur}:lp={blur}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                out_path,
            ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)


def _extract_frame_ffmpeg(input_path: str, at_sec: float = 0.5) -> bytes:
    ffmpeg = _get_ffmpeg()
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            str(max(0, at_sec)),
            "-i",
            input_path,
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-f",
            "image2",
            "pipe:1",
        ],
        capture_output=True,
        timeout=30,
    )
    return result.stdout if result.returncode == 0 and result.stdout else b""


def detect_plate_boxes(frame: np.ndarray, max_candidates: int = 3) -> list[Tuple[int, int, int, int]]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(HSV_LOWER_YELLOW, dtype=np.uint8), np.array(HSV_UPPER_YELLOW, dtype=np.uint8))
    mask_light = cv2.inRange(hsv, np.array(HSV_LOWER_LIGHT, dtype=np.uint8), np.array(HSV_UPPER_LIGHT, dtype=np.uint8))
    mask = cv2.bitwise_or(mask, mask_light)

    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame.shape[0] * frame.shape[1]
    candidates: list[Tuple[Tuple[int, int, int, int], float]] = []

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        ratio = w / h if h > 0 else 0

        if area < MIN_PLATE_AREA:
            continue
        if not (PLATE_MIN_RATIO < ratio < PLATE_MAX_RATIO):
            continue
        if area > frame_area * MAX_PLATE_AREA_RATIO:
            continue

        aspect_ratio_fit = min(1.0, max(0.0, 1.0 - min(abs(ratio - p["ratio"]) for p in PLATE_FORMAT_PRESETS) / 2.0))
        compactness = cv2.contourArea(contour) / area if area > 0 else 0
        compactness_fit = min(1.0, compactness)
        score = area * (0.5 + aspect_ratio_fit) * (0.5 + compactness_fit)
        candidates.append(((x, y, w, h), score))

    candidates.sort(key=lambda c: c[1], reverse=True)
    return [c[0] for c in candidates[:max_candidates]]


def detect_plate_box(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    boxes = detect_plate_boxes(frame, max_candidates=1)
    return boxes[0] if boxes else None


def _is_valid_israeli_plate(cleaned: str) -> bool:
    if re.search(r"[A-Za-z]", cleaned):
        return False
    digits = re.sub(r"[^0-9]", "", cleaned)
    return 7 <= len(digits) <= 8


def _preprocess_black_on_yellow(crop: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    return cv2.bitwise_not(binary)


def _crop_to_digit_region(crop: np.ndarray) -> np.ndarray:
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        ys, xs = np.where(binary > 0)
        if len(ys) < 20 or len(xs) < 20:
            return crop
        pad = 2
        y1 = max(0, int(ys.min()) - pad)
        y2 = min(crop.shape[0], int(ys.max()) + 1 + pad)
        x1 = max(0, int(xs.min()) - pad)
        x2 = min(crop.shape[1], int(xs.max()) + 1 + pad)
        if (y2 - y1) < 15 or (x2 - x1) < 30:
            return crop
        return crop[y1:y2, x1:x2].copy()
    except Exception:
        return crop


def _sharpen_denoise(crop: np.ndarray) -> np.ndarray:
    denoised = cv2.fastNlMeansDenoisingColored(crop, None, h=6, hForColorComponents=6, templateWindowSize=7, searchWindowSize=21)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    return cv2.filter2D(denoised, -1, kernel)


def _ocr_plate_crop(crop: np.ndarray, enhance_black_on_yellow: bool = True, debug_context: str = "") -> Tuple[Optional[str], Optional[str]]:
    if pytesseract is None:
        return (None, "Tesseract is not installed.")
    try:
        crop = _sharpen_denoise(crop)
        crop = _crop_to_digit_region(crop)
        if enhance_black_on_yellow:
            proc = _preprocess_black_on_yellow(crop)
        else:
            proc = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        config = "--psm 7 -c tessedit_char_whitelist=0123456789"
        text = pytesseract.image_to_string(proc, config=config)
        digits = re.sub(r"[^0-9]", "", text or "")
        return (digits or None, None)
    except Exception as e:
        return (None, str(e))


def _ocr_plate_from_frame_fast_hsv(frame: np.ndarray, debug_prefix: str = "") -> Tuple[Optional[str], Optional[str]]:
    plate_boxes = detect_plate_boxes(frame, max_candidates=3)
    if not plate_boxes:
        return (None, "No yellow plate region detected (HSV).")

    last_reason = None
    for i, plate_box in enumerate(plate_boxes):
        x, y, w, h = plate_box
        pad = max(2, min(w, h) // 8)
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(frame.shape[1], x + w + pad)
        y2 = min(frame.shape[0], y + h + pad)
        crop = frame[y1:y2, x1:x2]
        if crop.size < 100:
            last_reason = "Plate crop too small for OCR."
            continue

        if min(crop.shape[:2]) < 250:
            scale = 250 / min(crop.shape[:2])
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        ctx = f"{debug_prefix} candidate_{i}" if debug_prefix else f"candidate_{i}"
        digits, ocr_err = _ocr_plate_crop(crop, enhance_black_on_yellow=True, debug_context=ctx)
        if ocr_err:
            last_reason = ocr_err
            continue
        if digits and _is_valid_israeli_plate(digits):
            return (digits, None)
        if digits:
            last_reason = f"OCR read only '{digits}' ({len(digits)} digit(s)); Israeli plates have 7 or 8 digits."
            continue
        last_reason = "OCR returned no digits."

    return (None, last_reason or "No valid plate from any candidate.")


def _ocr_plate_from_frame(frame: np.ndarray, debug_prefix: str = "") -> Tuple[Optional[str], Optional[str]]:
    return _ocr_plate_from_frame_fast_hsv(frame, debug_prefix=debug_prefix)


def extract_license_plate(
    video_bytes: Optional[bytes] = None,
    frame_jpeg: Optional[bytes] = None,
    use_fast_hsv: bool = False,
    registry_lookup=None,
) -> Tuple[str, Optional[str]]:
    ocr_fn = _ocr_plate_from_frame_fast_hsv if use_fast_hsv else _ocr_plate_from_frame
    frame_tuples: list[Tuple[float, np.ndarray]] = []

    if frame_jpeg:
        frame = cv2.imdecode(np.frombuffer(frame_jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return ("11111", "Could not decode frame image.")
        plate, reason = ocr_fn(frame, debug_prefix="ticket_frame")
        if plate:
            return (plate, None)
        if not video_bytes:
            return ("11111", reason or "Plate detected visually; OCR could not read valid 7–8 digit number.")

    if not video_bytes:
        return ("11111", "No video or frame provided.")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    try:
        cap = cv2.VideoCapture(input_path)
        if cap.isOpened():
            for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()
                if ret and frame is not None:
                    frame_tuples.append((t, frame))
            cap.release()
        else:
            frame_jpeg_bytes = _extract_frame_ffmpeg(input_path, 0.5)
            if frame_jpeg_bytes:
                frame = cv2.imdecode(np.frombuffer(frame_jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    frame_tuples.append((0.5, frame))

        counter: Counter[str] = Counter()
        last_reason: Optional[str] = None

        def _registry_accepts(reg, p: str) -> bool:
            if reg is None:
                return True
            if hasattr(reg, "exists"):
                return reg.exists(p)
            if hasattr(reg, "plate_exists"):
                return reg.plate_exists(p)
            return True

        for t, frame in frame_tuples:
            plate, reason = ocr_fn(frame, debug_prefix=f"t={t:.1f}s")
            if plate and _is_valid_israeli_plate(plate):
                counter[plate] += 1
            last_reason = reason

        for plate, _ in counter.most_common():
            if _registry_accepts(registry_lookup, plate):
                return (plate, None)

        if counter:
            best = counter.most_common(1)[0][0]
            if registry_lookup is None:
                return (best, None)
            return ("11111", f"Most frequent OCR '{best}' not in registry.")

        return ("11111", last_reason or "Car or plate not detected; OCR could not read valid 7–8 digit number.")
    finally:
        Path(input_path).unlink(missing_ok=True)


def _expand_box(box: Tuple[int, int, int, int], frame_shape: Tuple[int, int, int], ratio: float = 0.20) -> Tuple[int, int, int, int]:
    x, y, w, h = box
    dh = int(h * ratio)
    dw = int(w * ratio)
    x1 = max(0, x - dw)
    y1 = max(0, y - dh)
    x2 = min(frame_shape[1], x + w + dw)
    y2 = min(frame_shape[0], y + h + dh)
    return x1, y1, x2 - x1, y2 - y1


def _apply_inverse_blur(frame: np.ndarray, plate_box: Optional[Tuple[int, int, int, int]], kernel: int) -> np.ndarray:
    """Blur everything except the plate ROI."""
    blurred = cv2.GaussianBlur(frame, (kernel, kernel), 0)
    if plate_box is None:
        return blurred

    x, y, w, h = _expand_box(plate_box, frame.shape, ratio=0.20)
    if w <= 0 or h <= 0:
        return blurred

    # Restore only the plate area to remain sharp.
    blurred[y:y + h, x:x + w] = frame[y:y + h, x:x + w]
    return blurred


def process_video(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
    pixel_block: int = 1,
    plate_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[bytes, bytes]:
    """Process video: detect plate first, keep plate visible, blur everything else."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            processed_bytes = _process_ffmpeg_only(input_path, blur=_normalize_blur_kernel(blur_strength))
            ticket_jpeg = _extract_frame_ffmpeg(input_path, 0.5)
            return processed_bytes, ticket_jpeg

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        raw_path = tempfile.mktemp(suffix=".mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(raw_path, fourcc, fps, (width, height))
        ticket_frame: Optional[np.ndarray] = None
        frame_idx_for_ticket = int(total_frames * extract_frame_at) if total_frames > 0 else 0
        frame_idx = 0
        k = _normalize_blur_kernel(blur_strength)
        tracker = PlateTracker()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_plate = plate_bbox or detect_plate_box(frame)
            tracked_plate = tracker.update(current_plate)
            output = _apply_inverse_blur(frame, tracked_plate, k)

            out.write(output)
            if frame_idx == frame_idx_for_ticket:
                ticket_frame = output.copy()
            frame_idx += 1

        cap.release()
        out.release()

        if frame_idx == 0:
            Path(raw_path).unlink(missing_ok=True)
            processed_bytes = _process_ffmpeg_only(input_path, blur=_normalize_blur_kernel(blur_strength))
            ticket_jpeg = _extract_frame_ffmpeg(input_path, 0.5)
            Path(input_path).unlink(missing_ok=True)
            return processed_bytes, ticket_jpeg

        out_path = tempfile.mktemp(suffix="_h264.mp4")
        try:
            ffmpeg = _get_ffmpeg()
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    raw_path,
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-an",
                    out_path,
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            processed_bytes = Path(out_path).read_bytes()
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode(errors="replace")[:500]
            raise ValueError(f"ffmpeg failed: {err}") from e
        finally:
            Path(raw_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

        ticket_jpeg = b""
        if ticket_frame is not None:
            ok, jpeg_buf = cv2.imencode(".jpg", ticket_frame)
            if ok:
                ticket_jpeg = jpeg_buf.tobytes()

        return processed_bytes, ticket_jpeg
    finally:
        Path(input_path).unlink(missing_ok=True)


def process_video_fast_hsv(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
) -> Tuple[bytes, bytes]:
    return process_video(video_bytes, blur_strength=blur_strength, extract_frame_at=extract_frame_at)


def process_video_with_violation_pipeline(
    video_bytes: bytes,
    output_dir: str | Path | None = None,
    extract_frame_at: float = 0.5,
    blur_kernel_size: int | None = None,
) -> Tuple[bytes, bytes, str]:
    """Simple wrapper that preserves repo API shape."""
    processed_video_bytes, ticket_frame_jpeg = process_video(
        video_bytes,
        blur_strength=int(blur_kernel_size or 0),
        extract_frame_at=extract_frame_at,
    )
    best_plate, _ = extract_license_plate(video_bytes=video_bytes, frame_jpeg=ticket_frame_jpeg, use_fast_hsv=True)
    return processed_video_bytes, ticket_frame_jpeg, best_plate
