"""Video processing for ticket review and privacy redaction.

This module must produce processed review video with the license plate region blurred.
It must never restore original plate pixels into the processed output.
"""
import json
import logging
import re
import shutil
import subprocess
from collections import Counter
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Any

import cv2

logger = logging.getLogger(__name__)
import numpy as np

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

# --- Ref config (from ref/config.py) — widened for better detection ---
HSV_LOWER_YELLOW = (10, 40, 40)   # Wider: catch dimmer/less saturated yellow
HSV_UPPER_YELLOW = (50, 255, 255)
HSV_LOWER_LIGHT = (15, 30, 150)   # Lighter/yellowish (lower saturation, higher value)
HSV_UPPER_LIGHT = (40, 255, 255)
PLATE_MIN_RATIO = 1.5
PLATE_MAX_RATIO = 7.0
MIN_PLATE_AREA = 200              # Allow smaller/distant plates
BLUR_KERNEL = 15                  # Lighter blur; odd number required (3=very light, 15=moderate, 51=strong)
MIN_BLUR_KERNEL = 15              # Minimum kernel so output is always visibly blurred (odd)
MAX_PLATE_AREA_RATIO = 0.08       # Reject implausibly large plate boxes; never restore original pixels
# Ref plate tracking (ALGORITHMS §2)
MAX_TRACK_MISSES = 8              # Reuse last box for up to N frames when detection misses
SMOOTHING_ALPHA = 0.65            # new_box = alpha*current + (1-alpha)*prev

# Israeli plate format presets (ref/examples/sample_plate_format.py)
PLATE_FORMAT_PRESETS = [
    {"name": "private_long", "ratio": 52 / 12, "width_cm": 52.0, "height_cm": 12.0},
    {"name": "private_rect", "ratio": 32 / 16, "width_cm": 32.0, "height_cm": 16.0},
    {"name": "motorcycle", "ratio": 17 / 16, "width_cm": 17.0, "height_cm": 16.0},
    {"name": "scooter", "ratio": 17 / 12, "width_cm": 17.0, "height_cm": 12.0},
]


def classify_plate_format(box_w: int, box_h: int) -> Optional[dict]:
    """Ref: map bbox ratio to Israeli plate format. Returns preset dict or None."""
    if box_h <= 0:
        return None
    ratio = box_w / box_h
    return min(PLATE_FORMAT_PRESETS, key=lambda p: abs(p["ratio"] - ratio))


class PlateTracker:
    """Ref ALGORITHMS §2: temporal smoothing and miss recovery for plate box."""
    def __init__(self, max_misses: int = MAX_TRACK_MISSES, alpha: float = SMOOTHING_ALPHA):
        self.max_misses = max_misses
        self.alpha = alpha
        self.last_box: Optional[Tuple[int, int, int, int]] = None
        self.miss_count = 0

    def update(self, box: Optional[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
        if box is not None:
            self.miss_count = 0
            if self.last_box is None:
                self.last_box = box
                return box
            # Smooth: new = alpha*current + (1-alpha)*prev
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


def _get_ffmpeg() -> str:
    """Return path to ffmpeg. Prefer imageio_ffmpeg, fallback to system ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        raise RuntimeError(
            "No ffmpeg found. Install imageio-ffmpeg (pip install imageio-ffmpeg) or add ffmpeg to PATH."
        )


def _get_ffprobe() -> Optional[str]:
    """Return path to ffprobe, or None if not found (same dir as ffmpeg or in PATH)."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    try:
        ffmpeg = _get_ffmpeg()
        # ffprobe often ships next to ffmpeg
        base = Path(ffmpeg).parent
        for name in ("ffprobe", "ffprobe.exe"):
            p = base / name
            if p.exists():
                return str(p)
    except RuntimeError:
        pass
    return None


def _parse_iso6709_location(s: str) -> Optional[dict]:
    """Parse ISO6709 location string (e.g. +32.0853+34.7818/) to {latitude, longitude}."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip().rstrip("/")
    # Pattern: +lat+lon or -lat-lon or +lat-lon etc.
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
    """
    Extract metadata from video file (duration, resolution, codec, GPS if present).
    Returns a JSON-serializable dict for Ticket.video_params.
    """
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

    # Format: duration, size, bit_rate, tags (may contain location)
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
    # Also check keys that contain 'location'
    if "gps_from_video" not in out:
        for k, val in tags.items():
            if "location" in k.lower() and val and isinstance(val, str):
                parsed = _parse_iso6709_location(val)
                if parsed:
                    out["gps_from_video"] = parsed
                    break

    # First video stream: width, height, codec, fps
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
    """Use ffmpeg to re-encode to H.264. blur=0 passes through, no blur."""
    ffmpeg = _get_ffmpeg()
    out_path = tempfile.mktemp(suffix="_h264.mp4")
    try:
        cmd = [ffmpeg, "-y", "-i", input_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", out_path]
        if blur > 0:
            cmd = [ffmpeg, "-y", "-i", input_path, "-vf", f"boxblur=lr={blur}:lp={blur}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", out_path]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)




def _normalize_blur_kernel(blur_strength: int = 0) -> int:
    """Normalize Gaussian blur kernel for OpenCV and privacy safety."""
    k = BLUR_KERNEL if BLUR_KERNEL % 2 == 1 else BLUR_KERNEL + 1
    if blur_strength > 0:
        k = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
    k = max(k, MIN_BLUR_KERNEL)
    if k % 2 == 0:
        k += 1
    return max(3, k)


def _clamp_box_to_frame(box: Tuple[int, int, int, int], frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Clamp a detected box to frame bounds and discard empty boxes."""
    x, y, w, h = box
    h_f, w_f = frame.shape[0], frame.shape[1]
    x = max(0, x)
    y = max(0, y)
    w = max(0, min(w, w_f - x))
    h = max(0, min(h, h_f - y))
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _apply_plate_blur(output: np.ndarray, plate_box: Optional[Tuple[int, int, int, int]], kernel: int) -> np.ndarray:
    """Blur only the plate ROI on the frame copy used for output."""
    if not plate_box:
        return output
    clamped = _clamp_box_to_frame(plate_box, output)
    if not clamped:
        return output
    x, y, w, h = clamped
    roi = output[y : y + h, x : x + w]
    roi_blurred = cv2.GaussianBlur(roi, (kernel, kernel), 0)
    output[y : y + h, x : x + w] = roi_blurred
    return output

def _extract_frame_ffmpeg(input_path: str, at_sec: float = 0.5) -> bytes:
    """Extract a frame at given time (seconds) as JPEG."""
    ffmpeg = _get_ffmpeg()
    result = subprocess.run(
        [ffmpeg, "-y", "-ss", str(max(0, at_sec)), "-i", input_path,
         "-vframes", "1", "-q:v", "2", "-f", "image2", "pipe:1"],
        capture_output=True,
        timeout=30,
    )
    return result.stdout if result.returncode == 0 and result.stdout else b""


def detect_plate_boxes(frame: np.ndarray, max_candidates: int = 3) -> list[Tuple[int, int, int, int]]:
    """
    Detect Israeli license plates using HSV yellow segmentation + contours.
    Returns top candidates (x, y, w, h) sorted by score for OCR fallback.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Primary: standard yellow
    mask = cv2.inRange(hsv, np.array(HSV_LOWER_YELLOW, dtype=np.uint8), np.array(HSV_UPPER_YELLOW, dtype=np.uint8))
    # Secondary: lighter/yellowish (wear, sun, different lighting)
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
        aspect_ratio_fit = min(1.0, max(0, 1.0 - min(abs(ratio - p["ratio"]) for p in PLATE_FORMAT_PRESETS) / 2.0))
        compactness = cv2.contourArea(contour) / area if area > 0 else 0
        compactness_fit = min(1.0, compactness)
        score = area * (0.5 + aspect_ratio_fit) * (0.5 + compactness_fit)
        candidates.append(((x, y, w, h), score))
    candidates.sort(key=lambda c: c[1], reverse=True)
    return [c[0] for c in candidates[:max_candidates]]


def detect_plate_box(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Return best plate box (x, y, w, h) or None."""
    boxes = detect_plate_boxes(frame, max_candidates=1)
    return boxes[0] if boxes else None


def _is_valid_israeli_plate(cleaned: str) -> bool:
    """Israeli plates: digits only, 7-8 chars."""
    if re.search(r"[A-Za-z]", cleaned):
        return False
    digits = re.sub(r"[^0-9]", "", cleaned)
    return 7 <= len(digits) <= 8


def _preprocess_black_on_yellow(crop: np.ndarray) -> np.ndarray:
    """Enhance black digits on yellow background for OCR. Returns grayscale image with inverted digits."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold to separate dark digits from bright yellow
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    # Invert: black digits on white background (Tesseract prefers this)
    return cv2.bitwise_not(binary)


def _crop_to_digit_region(crop: np.ndarray) -> np.ndarray:
    """Extract only the digit region from a plate crop. Removes yellow border, EU strip, etc.
    Returns tighter crop for better OCR; falls back to original if extraction fails."""
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Threshold: dark pixels = digits
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
    """Sharpen edges and reduce noise to improve OCR on slightly blurry plates."""
    denoised = cv2.fastNlMeansDenoisingColored(crop, None, h=6, hForColorComponents=6, templateWindowSize=7, searchWindowSize=21)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    return sharpened


def _crop_to_digit_region(crop: np.ndarray) -> np.ndarray:
    """
    Extract only the digit region from the plate crop.
    Reduces yellow border/EU strip/noise - improves OCR accuracy and performance.
    Returns tight crop around dark (digit) pixels, or original if extraction fails.
    """
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # Threshold: digits are darker than yellow background
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        # Dark pixels (digits) are black (0)
        ys, xs = np.where(binary > 0)
        if len(ys) < 20 or len(xs) < 20:
            return crop
        y_min, y_max = int(ys.min()), int(ys.max()) + 1
        x_min, x_max = int(xs.min()), int(xs.max()) + 1
        # Require reasonable digit region (at least 15px in each dim)
        if (y_max - y_min) < 15 or (x_max - x_min) < 15:
            return crop
        # Small pad for safety
        pad = 2
        h, w = crop.shape[:2]
        y1 = max(0, y_min - pad)
        y2 = min(h, y_max + pad)
        x1 = max(0, x_min - pad)
        x2 = min(w, x_max + pad)
        tight = crop[y1:y2, x1:x2]
        if tight.size < 100:
            return crop
        return tight
    except Exception:
        return crop


def _get_ocr_preprocess_variants(crop: np.ndarray) -> list[Tuple[np.ndarray, str]]:
    """Return list of (preprocessed_image, label) to try when primary preprocessing fails."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    variants: list[Tuple[np.ndarray, str]] = []

    # 0. Sharpen + denoise then black-on-yellow - helps blurry/mobile footage
    try:
        enhanced = _sharpen_denoise(crop)
        variants.append((_preprocess_black_on_yellow(enhanced), "sharpen_denoise+boy"))
    except Exception:
        pass

    # 1. Raw grayscale - sometimes default works when adaptive over-processes
    variants.append((gray, "raw_gray"))

    # 2. CLAHE for contrast then adaptive (also try stronger clipLimit for low-contrast plates)
    try:
        for clip, label in [(2.0, "clahe+adaptive"), (4.0, "clahe_strong+adaptive")]:
            clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
            binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            variants.append((cv2.bitwise_not(binary), label))
    except Exception:
        pass

    # 3. Otsu threshold - works well when bimodal (digits vs background). Try both polarities.
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append((otsu, "otsu"))
    variants.append((cv2.bitwise_not(otsu), "otsu_inv"))

    # 4. Lighter adaptive (larger block, more tolerance)
    binary_wide = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 5)
    variants.append((cv2.bitwise_not(binary_wide), "adaptive_wide"))

    # 5. Simple threshold at midpoint - for high-contrast images
    mid = int(gray.mean())
    _, simple = cv2.threshold(gray, mid, 255, cv2.THRESH_BINARY)
    variants.append((simple, "simple_thresh"))

    return variants


def _ocr_plate_crop(
    crop: np.ndarray,
    enhance_black_on_yellow: bool = True,
    debug_context: str = "",
) -> Tuple[str, Optional[str]]:
    """Run Tesseract OCR on plate crop. Israeli plates: black digits on yellow.
    Tries multiple preprocessing strategies when primary returns no digits.
    When debug_context is set, logs which method/PSM succeeded."""
    if pytesseract is None:
        return "", "Tesseract OCR not available. Install: winget install UB-Mannheim.TesseractOCR"
    if crop.size == 0:
        return "", "Plate crop is empty."
    ctx = f" [{debug_context}]" if debug_context else ""

    def _run_ocr(img: np.ndarray) -> str:
        text = pytesseract.image_to_string(
            img,
            config="--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789",
        )
        return re.sub(r"[^0-9]", "", text.strip())

    def _run_ocr_psm(img: np.ndarray, psm: int) -> str:
        try:
            text = pytesseract.image_to_string(
                img,
                config=f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789",
            )
            return re.sub(r"[^0-9]", "", text.strip())
        except Exception:
            return ""

    try:
        # Primary: sharpen+denoise then black-on-yellow (helps blurry mobile footage)
        if enhance_black_on_yellow:
            try:
                enhanced = _sharpen_denoise(crop)
                img = _preprocess_black_on_yellow(enhanced)
                if img is not None and img.size > 0:
                    digits = _run_ocr(img)
                    if digits:
                        logger.info("Plate OCR%s: method=sharpen_denoise+boy psm=7 digits=%s", ctx, digits)
                        return digits, None
            except Exception:
                pass
        # Standard black-on-yellow
        img = _preprocess_black_on_yellow(crop) if enhance_black_on_yellow else crop
        if img is None or img.size == 0:
            img = crop
        digits = _run_ocr(img)
        if digits:
            logger.info("Plate OCR%s: method=black_on_yellow psm=7 digits=%s", ctx, digits)
            return digits, None

        # Fallback: try alternative preprocessing
        for variant_img, label in _get_ocr_preprocess_variants(crop):
            digits = _run_ocr(variant_img)
            if digits:
                logger.info("Plate OCR%s: method=%s psm=7 digits=%s", ctx, label, digits)
                return digits, None

        # Last resort: PSM 6 and PSM 8 on primary preprocessed image (single word mode helps some plates)
        img = _preprocess_black_on_yellow(crop) if enhance_black_on_yellow else crop
        if img is not None and img.size > 0:
            for psm in (6, 8):
                digits = _run_ocr_psm(img, psm)
                if digits:
                    logger.info("Plate OCR%s: method=black_on_yellow psm=%s digits=%s", ctx, psm, digits)
                    return digits, None

        return "", None
    except Exception as e:
        err = str(e)
        if "TesseractNotFoundError" in type(e).__name__ or "tesseract" in err.lower():
            return "", f"Tesseract not installed or not in PATH: {err}"
        return "", f"OCR error: {err}"


_vehicle_detector = None


def _get_vehicle_detector():
    """Lazy-load YOLO vehicle detector."""
    global _vehicle_detector
    if _vehicle_detector is None:
        from app.config import settings
        from app.violation.services.detector import VehicleDetector
        path = getattr(settings, "yolo_model_path", "yolov8n.pt")
        _vehicle_detector = VehicleDetector(path)
    return _vehicle_detector


def _detect_plate_in_region(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Optional[Tuple[int, int, int, int]]:
    """Detect plate (x,y,w,h) within a region. Plates usually at lower part of vehicle."""
    h_total, w_total = frame.shape[:2]
    # Restrict to region, with plate typically in lower half of vehicle
    region = frame[y1:y2, x1:x2]
    if region.size == 0:
        return None
    box = detect_plate_box(region)
    if not box:
        return None
    rx, ry, rw, rh = box
    # Convert to full frame coords
    return (x1 + rx, y1 + ry, rw, rh)


def _get_plate_box(frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Get plate box (x,y,w,h) for blur: car->plate flow, fallback to HSV. Keeps plate sharp."""
    try:
        detector = _get_vehicle_detector()
        vehicles = detector.detect_and_track(frame)
    except Exception:
        vehicles = []
    primary = None
    best_area = 0
    for v in vehicles:
        x1, y1, x2, y2 = v.bbox
        area = (x2 - x1) * (y2 - y1)
        if area > best_area and v.confidence >= 0.4:
            best_area = area
            primary = v
    plate_box = None
    if primary:
        x1, y1, x2, y2 = primary.bbox
        h_car = y2 - y1
        plate_region_bottom = y1 + int(h_car * 0.5)
        plate_box = _detect_plate_in_region(frame, x1, plate_region_bottom, x2, y2)
    if not plate_box:
        plate_box = detect_plate_box(frame)
    return plate_box


def _ocr_plate_from_frame(frame: np.ndarray, debug_prefix: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Identify car -> zoom to plate -> OCR only plate digits.
    Returns (plate, failure_reason). plate is None when not found.
    """
    # 1. Detect vehicles
    try:
        detector = _get_vehicle_detector()
        vehicles = detector.detect_and_track(frame)
    except Exception as e:
        vehicles = []
    # 2. Pick primary car (largest bbox)
    primary = None
    best_area = 0
    for v in vehicles:
        x1, y1, x2, y2 = v.bbox
        area = (x2 - x1) * (y2 - y1)
        if area > best_area and v.confidence >= 0.4:
            best_area = area
            primary = v
    # 3. Find plate: within vehicle or fallback to full-frame HSV
    plate_box = None
    if primary:
        x1, y1, x2, y2 = primary.bbox
        h_car = y2 - y1
        plate_region_bottom = y1 + int(h_car * 0.5)
        plate_box = _detect_plate_in_region(frame, x1, plate_region_bottom, x2, y2)
    if not plate_box:
        plate_box = detect_plate_box(frame)
    if not plate_box:
        if not vehicles:
            return (None, "No vehicle detected in frame (YOLO).")
        return (None, "No yellow plate region detected (HSV).")
    x, y, w, h = plate_box
    # 4. Zoom: crop tightly to plate only
    pad = max(2, min(w, h) // 8)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(frame.shape[1], x + w + pad)
    y2 = min(frame.shape[0], y + h + pad)
    crop = frame[y1:y2, x1:x2]
    if crop.size < 100:
        return (None, "Plate crop too small for OCR.")
    # 5. Enlarge if too small (Tesseract reads digits better at 250px min)
    if min(crop.shape[:2]) < 250:
        scale = 250 / min(crop.shape[:2])
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    digits, ocr_err = _ocr_plate_crop(crop, debug_context=debug_prefix)
    if ocr_err:
        return (None, ocr_err)
    if _is_valid_israeli_plate(digits):
        return (digits, None)
    if digits:
        return (None, f"OCR read '{digits}' but need 7-8 digits for Israeli plate.")
    return (None, "OCR returned no digits.")


def _ocr_plate_from_frame_fast_hsv(frame: np.ndarray, debug_prefix: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Fast path: HSV yellow plate only, no YOLO. Tries top plate candidates; black-on-yellow OCR.
    Returns (plate, failure_reason). plate is None when not found.
    """
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
        # Enlarge small crops: Tesseract reads digits better at ~250px min dimension
        if min(crop.shape[:2]) < 250:
            scale = 250 / min(crop.shape[:2])
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        ctx = f"{debug_prefix} candidate_{i}" if debug_prefix else f"candidate_{i}"
        digits, ocr_err = _ocr_plate_crop(crop, enhance_black_on_yellow=True, debug_context=ctx)
        if ocr_err:
            last_reason = ocr_err
            continue
        if _is_valid_israeli_plate(digits):
            return (digits, None)
        if digits:
            last_reason = f"OCR read '{digits}' but need 7-8 digits for Israeli plate."
            continue
        last_reason = "OCR returned no digits."
    return (None, last_reason or "No valid plate from any candidate.")


def extract_license_plate(
    video_bytes: Optional[bytes] = None,
    frame_jpeg: Optional[bytes] = None,
    use_fast_hsv: bool = False,
    registry_lookup=None,
) -> Tuple[str, Optional[str]]:
    """
    Identify plate after blurring: run OCR on the sharp plate region.
    Pass frame_jpeg (processed/blurred frame) to OCR exactly what user sees.
    Or pass video_bytes to sample frames from source.
    use_fast_hsv: use HSV-only plate detection (no YOLO) and black-on-yellow OCR.
    registry_lookup: optional object with exists(plate) for OCR voting (ref: pick most frequent valid).
    Returns (plate, reason). plate=11111 when not found.
    """
    ocr_fn = _ocr_plate_from_frame_fast_hsv if use_fast_hsv else _ocr_plate_from_frame
    frame_tuples: list[Tuple[float, np.ndarray]] = []

    if frame_jpeg:
        frame = cv2.imdecode(np.frombuffer(frame_jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return ("11111", "Could not decode frame image.")
        plate, reason = ocr_fn(frame, debug_prefix="ticket_frame")
        if plate:
            return (plate, None)
        # If frame failed but we have video_bytes, try multiple frames (better plate visibility at different times)
        if not video_bytes:
            return ("11111", reason or "Plate detected visually; OCR could not read valid 7–8 digit number.")

    if not video_bytes:
        return ("11111", "No video or frame provided.")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name
    try:
        cap = cv2.VideoCapture(input_path)
        frame_tuples: list[Tuple[float, np.ndarray]] = []
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

        # Ref: OCR voting — collect all valid 7–8 digit reads, pick most frequent that exists in registry
        from collections import Counter
        counter: Counter[str] = Counter()
        last_reason: Optional[str] = None
        for t, frame in frame_tuples:
            plate, reason = ocr_fn(frame, debug_prefix=f"t={t:.1f}s")
            if plate and _is_valid_israeli_plate(plate):
                counter[plate] += 1
            last_reason = reason

        def _registry_accepts(reg, p: str) -> bool:
            if reg is None:
                return True
            if hasattr(reg, "exists"):
                return reg.exists(p)
            if hasattr(reg, "plate_exists"):
                return reg.plate_exists(p)
            return True

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


def process_video(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
    pixel_block: int = 1,
    plate_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[bytes, bytes]:
    """
    Process video: HSV plate detection per frame, blur only the plate ROI (privacy).
    plate_bbox: ignored (ref detects per-frame). Kept for API compatibility.
    """
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

            output = frame.copy()
            plate_box = tracker.update(_get_plate_box(frame))
            output = _apply_plate_blur(output, plate_box, k)

            out.write(output)
            if frame_idx == frame_idx_for_ticket:
                ticket_frame = output.copy()
            frame_idx += 1

        cap.release()
        out.release()

        # If OpenCV read no frames (e.g. codec not supported), fall back to full-frame ffmpeg blur
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
                    ffmpeg, "-y", "-i", raw_path,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an",
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
            _, jpeg_buf = cv2.imencode(".jpg", ticket_frame)
            ticket_jpeg = jpeg_buf.tobytes()
    finally:
        Path(input_path).unlink(missing_ok=True)

    return processed_bytes, ticket_jpeg


def process_video_fast_hsv(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
) -> Tuple[bytes, bytes]:
    """
    Fast HSV pipeline: no YOLO. Detect yellow plates via HSV only, blur only the plate ROI.
    Uses black-on-yellow OCR preprocessing. Faster than process_video (skips vehicle detection).
    """
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

            output = frame.copy()
            plate_box = tracker.update(detect_plate_box(frame))
            output = _apply_plate_blur(output, plate_box, k)

            out.write(output)
            if frame_idx == frame_idx_for_ticket:
                ticket_frame = output.copy()
            frame_idx += 1

        cap.release()
        out.release()

        # If OpenCV read no frames (e.g. codec not supported), fall back to full-frame ffmpeg blur
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
                    ffmpeg, "-y", "-i", raw_path,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an",
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
            _, jpeg_buf = cv2.imencode(".jpg", ticket_frame)
            ticket_jpeg = jpeg_buf.tobytes()
    finally:
        Path(input_path).unlink(missing_ok=True)

    return processed_bytes, ticket_jpeg


def _find_parked_zones(
    input_path: str,
    detector,
    interval_sec: float = 10.0,
    match_radius_px: float = 60.0,
) -> list[Tuple[float, float, float]]:
    """
    Sample video at interval_sec (e.g. 10s). Vehicles at same location in 2+ samples = parked.
    Returns list of (center_x, center_y, radius) zones where a car was stationary.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return []
    duration_sec = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(1, cap.get(cv2.CAP_PROP_FPS) or 25)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    radius = max(match_radius_px, 0.05 * min(width, height))

    samples: list[tuple[float, list[tuple[int, int, int, int]]]] = []
    t = 0.0
    while t < duration_sec - 0.5:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        detections = detector.detect(frame)
        bboxes = [(v.bbox[0], v.bbox[1], v.bbox[2], v.bbox[3]) for v in detections if v.confidence >= 0.4]
        samples.append((t, bboxes))
        t += interval_sec
    cap.release()

    if len(samples) < 2:
        return []

    def bbox_center(b):
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

    def centers_match(c1, c2):
        return (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 <= radius ** 2

    parked_zones: list[Tuple[float, float, float]] = []
    for t0, boxes0 in samples:
        for bbox in boxes0:
            c0 = bbox_center(bbox)
            seen_same = False
            for t1, boxes1 in samples:
                if t1 <= t0:
                    continue
                for b1 in boxes1:
                    if centers_match(c0, bbox_center(b1)):
                        seen_same = True
                        break
                if seen_same:
                    break
            if seen_same and not any(
                (c0[0] - px) ** 2 + (c0[1] - py) ** 2 <= (r * 1.5) ** 2
                for px, py, r in parked_zones
            ):
                parked_zones.append((c0[0], c0[1], radius))
    return parked_zones


def process_video_with_violation_pipeline(
    video_bytes: bytes,
    output_dir: str | Path | None = None,
    extract_frame_at: float = 0.5,
    blur_kernel_size: int | None = None,
) -> Tuple[bytes, bytes, str]:
    """
    Process video through full violation pipeline: YOLO detection, curb distance, selective blur.
    Identifies parked cars via 10s-interval sampling: if car doesn't move between samples, it's parked.
    Returns (processed_video_bytes, ticket_frame_jpeg, best_plate).
    Falls back to ref process_video on error.
    """
    from app.config import settings
    from app.violation.pipeline import ParkingViolationPipeline
    from app.violation.services.detector import VehicleDetector

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name
    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return process_video(video_bytes, blur_strength=0, extract_frame_at=extract_frame_at) + ("11111",)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_dir = tempfile.mkdtemp() if output_dir is None else str(output_dir)

        detector = VehicleDetector(getattr(settings, 'yolo_model_path', 'yolov8n.pt'))
        interval_sec = getattr(settings, 'parking_check_interval_sec', 10.0)
        parked_zones = _find_parked_zones(input_path, detector, interval_sec=interval_sec)
        pipeline = ParkingViolationPipeline(
            output_dir=out_dir, parked_zones=parked_zones, blur_kernel_size=blur_kernel_size
        )

        raw_path = tempfile.mktemp(suffix=".mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(raw_path, fourcc, fps, (width, height))

        best_plate = "11111"
        ticket_frame: Optional[np.ndarray] = None
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        frame_idx_for_ticket = int(total_frames * extract_frame_at) if total_frames > 0 else 0
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out_frame, frame_result = pipeline.process_frame(frame, frame_idx + 1)
            writer.write(out_frame)
            for d in frame_result.decisions:
                if d.plate and d.plate.text:
                    best_plate = d.plate.text
            if frame_idx == frame_idx_for_ticket and frame_result.decisions:
                ticket_frame = out_frame.copy()
            frame_idx += 1

        cap.release()
        writer.release()

        out_path = tempfile.mktemp(suffix="_h264.mp4")
        try:
            ffmpeg = _get_ffmpeg()
            subprocess.run(
                [ffmpeg, "-y", "-i", raw_path, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", "-an", out_path],
                check=True, capture_output=True, timeout=300,
            )
            processed_bytes = Path(out_path).read_bytes()
        finally:
            Path(raw_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

        if ticket_frame is None:
            cap2 = cv2.VideoCapture(input_path)
            if cap2.isOpened():
                cap2.set(cv2.CAP_PROP_POS_MSEC, extract_frame_at * 1000)
                _, ticket_frame = cap2.read()
                cap2.release()
        ticket_jpeg = b""
        if ticket_frame is not None:
            _, jpeg_buf = cv2.imencode(".jpg", ticket_frame)
            ticket_jpeg = jpeg_buf.tobytes()

        return processed_bytes, ticket_jpeg, best_plate
    except Exception:
        return process_video(video_bytes, blur_strength=0, extract_frame_at=extract_frame_at) + ("11111",)
    finally:
        Path(input_path).unlink(missing_ok=True)
