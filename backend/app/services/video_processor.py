from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np

try:
    import pytesseract
except Exception:
    pytesseract = None


BLUR_KERNEL = 21
TRACK_MISSES = 10
SMOOTH_ALPHA = 0.70

# Israeli plates: bright yellow background, H 15-38, S>=80, V>=100.
# Conservative range avoids false positives on sand/ground/road markings.
# Edge-density + pos scoring handles remaining candidates.
HSV_LOWER_YELLOW = (15, 80, 100)
HSV_UPPER_YELLOW = (38, 255, 255)

# Red/white curb detection
HSV_RED_LO1  = (0,   80,  80)
HSV_RED_HI1  = (10,  255, 255)
HSV_RED_LO2  = (160, 80,  80)
HSV_RED_HI2  = (180, 255, 255)
HSV_WHITE_LO = (0,   0,   180)
HSV_WHITE_HI = (180, 50,  255)

BBox = Tuple[int, int, int, int]


@dataclass
class PlateTracker:
    max_misses: int = TRACK_MISSES
    alpha: float = SMOOTH_ALPHA

    def __post_init__(self) -> None:
        self.last_box: Optional[BBox] = None
        self.miss_count = 0

    # ── IoU helper (from test engine) ──────────────────────────────────────
    @staticmethod
    def _iou(a: BBox, b: BBox) -> float:
        """IoU between two xywh boxes."""
        ax1, ay1 = a[0], a[1]
        ax2, ay2 = a[0] + a[2], a[1] + a[3]
        bx1, by1 = b[0], b[1]
        bx2, by2 = b[0] + b[2], b[1] + b[3]
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def update(self, box: Optional[BBox]) -> Optional[BBox]:
        if box is not None:
            self.miss_count = 0
            if self.last_box is None:
                self.last_box = box
                return box
            lx, ly, lw, lh = self.last_box
            x = int(self.alpha * box[0] + (1 - self.alpha) * lx)
            y = int(self.alpha * box[1] + (1 - self.alpha) * ly)
            w = int(self.alpha * box[2] + (1 - self.alpha) * lw)
            h = int(self.alpha * box[3] + (1 - self.alpha) * lh)
            self.last_box = (x, y, w, h)
            return self.last_box
        self.miss_count += 1
        if self.miss_count > self.max_misses:
            self.last_box = None
            return None
        return self.last_box


def _normalize_kernel(k: int) -> int:
    if k < 3:
        k = BLUR_KERNEL
    if k % 2 == 0:
        k += 1
    return k


def _safe_denoise_and_sharpen(img: np.ndarray) -> np.ndarray:
    try:
        denoised = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)
    except Exception:
        denoised = img
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
    return cv2.filter2D(denoised, -1, kernel)


def get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        raise RuntimeError("ffmpeg not found")


def get_ffprobe() -> Optional[str]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    try:
        ffmpeg = get_ffmpeg()
        base = Path(ffmpeg).parent
        for name in ("ffprobe", "ffprobe.exe"):
            p = base / name
            if p.exists():
                return str(p)
    except Exception:
        pass
    return None


def extract_video_params(input_path: str) -> dict:
    ffprobe = get_ffprobe()
    if not ffprobe:
        return {}
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-show_format",
                "-show_streams",
                "-print_format", "json",
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0 or not result.stdout:
            return {}
        data = json.loads(result.stdout)
        out: dict[str, Any] = {}
        fmt = data.get("format") or {}
        if fmt.get("duration"):
            try:
                out["duration_sec"] = round(float(fmt["duration"]), 2)
            except Exception:
                pass
        if fmt.get("size"):
            try:
                out["size_bytes"] = int(fmt["size"])
            except Exception:
                pass
        if fmt.get("bit_rate") and fmt["bit_rate"] != "N/A":
            try:
                out["bit_rate"] = int(fmt["bit_rate"])
            except Exception:
                pass
        for stream in data.get("streams") or []:
            if stream.get("codec_type") == "video":
                try:
                    out["width"] = int(stream.get("width") or 0)
                    out["height"] = int(stream.get("height") or 0)
                except Exception:
                    pass
                if stream.get("codec_name"):
                    out["codec"] = str(stream["codec_name"])
                break
        return out
    except Exception:
        return {}


def _best_plate_from_mask(
    mask: np.ndarray,
    frame_shape: tuple,
    frame_gray: Optional[np.ndarray] = None,
    prev_box: Optional[BBox] = None,
) -> Optional[BBox]:
    """Find the best plate bounding box from a binary mask.

    Scoring (adapted from test engine):
      score = area×0.01 + edge_density×40 + pos_score×10 + iou_bonus×35
    - edge_density rejects large flat regions (sand, sky, road)
    - pos_score rewards candidates near image centre-lower area
    - iou_bonus rewards temporal continuity with the previous known box
    """
    # Smaller kernels than before: 3×3 OPEN + 7×7 CLOSE.
    # Smaller OPEN avoids erasing small distant plates.
    kernel_open  = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel_open)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_frame, w_frame = frame_shape[:2]

    # Prepare grayscale for edge density if not supplied
    best: Optional[BBox] = None
    best_score = -1e9

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if w < 25 or h < 8:
            continue
        ratio = w / float(h) if h > 0 else 0.0
        # Israeli plates ~52×11.4 cm → ratio ≈ 4.6; allow 2.5–7.0
        if ratio < 2.5 or ratio > 7.0:
            continue

        # Edge density — plates have lots of edges (characters); sky/sand/ground do not
        edge_density = 0.0
        if frame_gray is not None:
            roi_edge = cv2.Canny(frame_gray[y:y + h, x:x + w], 80, 200)
            edge_density = float(roi_edge.mean() / 255.0)

        # Position score: reward candidates near horizontal centre, vertical 60% down
        cx = (x + w / 2.0)
        cy = (y + h / 2.0)
        pos_score = (
            (1.0 - abs(cx - w_frame * 0.5) / max(w_frame * 0.5, 1)) * 0.6
            + (1.0 - abs(cy - h_frame * 0.6) / max(h_frame * 0.6, 1)) * 0.4
        )

        # IoU bonus: reward continuity with the previous detected box
        iou_bonus = 0.0
        if prev_box is not None:
            px, py, pw, ph = prev_box
            prev_xyxy = (px, py, px + pw, py + ph)
            cur_xyxy  = (x,  y,  x + w,  y + h)
            ix1, iy1 = max(prev_xyxy[0], cur_xyxy[0]), max(prev_xyxy[1], cur_xyxy[1])
            ix2, iy2 = min(prev_xyxy[2], cur_xyxy[2]), min(prev_xyxy[3], cur_xyxy[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_p = pw * ph
            area_c = w * h
            union = area_p + area_c - inter
            iou_bonus = (inter / union if union > 0 else 0.0) * 35.0

        score = area * 0.01 + edge_density * 40.0 + pos_score * 10.0 + iou_bonus
        if score > best_score:
            best_score = score
            best = (x, y, w, h)

    return best


def detect_plate_box(
    frame: np.ndarray,
    prev_box: Optional[BBox] = None,
) -> Optional[BBox]:
    """Detect license plate in frame.
    Tries yellow plates (standard Israeli) first, then white plates (commercial/diplomatic).
    Uses edge-density + position scoring; prev_box adds IoU continuity bonus.
    Returns best bounding box or None.
    """
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # --- Yellow plates (standard Israeli) ---
    yellow_mask = cv2.inRange(
        hsv,
        np.array(HSV_LOWER_YELLOW, dtype=np.uint8),
        np.array(HSV_UPPER_YELLOW, dtype=np.uint8),
    )
    best = _best_plate_from_mask(yellow_mask, frame.shape, frame_gray=gray, prev_box=prev_box)
    if best is not None:
        return best

    # --- White plates (commercial, diplomatic, electric vehicles) ---
    white_mask = cv2.inRange(
        hsv,
        np.array([0, 0, 140], dtype=np.uint8),
        np.array([180, 60, 255], dtype=np.uint8),
    )
    return _best_plate_from_mask(white_mask, frame.shape, frame_gray=gray, prev_box=prev_box)


def detect_redwhite_curb(frame: np.ndarray) -> Optional[BBox]:
    """Detect red-and-white striped no-parking curb marking.

    Returns bounding box of the curb region, or None if not found.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, np.array(HSV_RED_LO1,  dtype=np.uint8), np.array(HSV_RED_HI1,  dtype=np.uint8))
    red2 = cv2.inRange(hsv, np.array(HSV_RED_LO2,  dtype=np.uint8), np.array(HSV_RED_HI2,  dtype=np.uint8))
    red_mask   = cv2.bitwise_or(red1, red2)
    white_mask = cv2.inRange(hsv, np.array(HSV_WHITE_LO, dtype=np.uint8), np.array(HSV_WHITE_HI, dtype=np.uint8))

    h_frame = frame.shape[0]
    dil_k = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(3, frame.shape[1] // 40), max(3, h_frame // 30)),
    )
    red_dil   = cv2.dilate(red_mask,   dil_k)
    white_dil = cv2.dilate(white_mask, dil_k)

    curb_mask = cv2.bitwise_and(red_dil, white_dil)
    close_k = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(5, frame.shape[1] // 20), max(5, h_frame // 20)),
    )
    curb_mask = cv2.morphologyEx(curb_mask, cv2.MORPH_CLOSE, close_k)

    contours, _ = cv2.findContours(curb_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best: Optional[BBox] = None
    best_score = 0.0
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < frame.shape[1] // 10:
            continue
        if h > 0 and (w / float(h)) < 1.5:
            continue
        score = float(w * h)
        if score > best_score:
            best_score = score
            best = (x, y, w, h)
    return best


def detect_plate_near_curb(
    frame: np.ndarray,
    curb_box: Optional[BBox],
    prev_box: Optional[BBox] = None,
) -> Optional[BBox]:
    """Find yellow plate on the car parked next to the curb.

    Searches the region above/around the curb first; falls back to
    full-frame search when nothing is found there.
    prev_box is passed to the scorer for IoU continuity bonus.
    """
    h_frame, w_frame = frame.shape[:2]
    if curb_box is not None:
        cx, cy, cw, ch = curb_box
        sy1 = max(0, cy - int(h_frame * 0.70))
        sy2 = min(h_frame, cy + ch + int(h_frame * 0.05))
        sx1 = max(0, cx - int(cw * 0.20))
        sx2 = min(w_frame, cx + cw + int(cw * 0.20))
        region = frame[sy1:sy2, sx1:sx2]
        # Translate prev_box into region coordinates for IoU bonus
        region_prev = None
        if prev_box is not None:
            rpx = prev_box[0] - sx1
            rpy = prev_box[1] - sy1
            region_prev = (rpx, rpy, prev_box[2], prev_box[3])
        box = detect_plate_box(region, prev_box=region_prev)
        if box is not None:
            bx, by, bw, bh = box
            return (sx1 + bx, sy1 + by, bw, bh)
    return detect_plate_box(frame, prev_box=prev_box)


def _expand_box(box: BBox, frame_shape: Tuple[int, int, int], ratio: float = 0.5) -> BBox:
    x, y, w, h = box
    dw = int(w * ratio)
    dh = int(h * ratio)
    x1 = max(0, x - dw)
    y1 = max(0, y - dh)
    x2 = min(frame_shape[1], x + w + dw)
    y2 = min(frame_shape[0], y + h + dh)
    return x1, y1, x2 - x1, y2 - y1


def _blur_everything_except_plate(frame: np.ndarray, plate_box: Optional[BBox], kernel: int) -> np.ndarray:
    """Blur the entire frame; restore the plate region unblurred.
    When no plate box is found, return the original frame unblurred so the
    relevant plate is never accidentally hidden.
    Uses ratio=2.0 expansion to keep a generous clear zone around the plate.
    """
    if plate_box is None:
        # Detection failed — show original so the relevant plate stays visible
        return frame
    blurred = cv2.GaussianBlur(frame, (kernel, kernel), 0)
    x, y, w, h = _expand_box(plate_box, frame.shape, ratio=1.2)
    if w <= 0 or h <= 0:
        return frame
    blurred[y:y + h, x:x + w] = frame[y:y + h, x:x + w].copy()
    return blurred


def _quick_ocr_plate_crop(crop: np.ndarray) -> str:
    """Run a quick OCR pass on a plate crop; return digit string or ''."""
    if crop is None or crop.size == 0:
        return ""
    # Try EasyOCR first (already loaded by anpr_pipeline)
    try:
        from app.services.anpr_pipeline import read_plate_crop
        digits, conf = read_plate_crop(crop)
        if digits and 7 <= len(digits) <= 8:
            return digits
    except Exception:
        pass
    # Tesseract fallback
    if pytesseract is not None:
        try:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()
            gray = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(
                binary,
                config="--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789",
            )
            digits = _clean_ocr_text(text or "")
            if 7 <= len(digits) <= 8:
                return digits
        except Exception:
            pass
    return ""


def _overlay_plate_magnified(
    frame: np.ndarray,
    plate_box: BBox,
    target_h: int = 120,
    original_frame: Optional[np.ndarray] = None,
    plate_text: Optional[str] = None,
) -> np.ndarray:
    """Crop the plate region and paste a magnified version in the top-left corner.
    Also renders the plate number text below the zoomed crop.
    If original_frame is provided, the crop is taken from it (unblurred source).
    """
    # Expand slightly to avoid clipping plate edges
    px, py, pw, ph = _expand_box(plate_box, frame.shape, ratio=0.20)
    if pw <= 0 or ph <= 0:
        return frame
    src = original_frame if original_frame is not None else frame
    crop = src[py:py + ph, px:px + pw]
    if crop.size == 0:
        return frame
    scale = target_h / ph
    new_w = max(1, int(pw * scale))
    zoomed = cv2.resize(crop, (new_w, target_h), interpolation=cv2.INTER_CUBIC)

    # Text strip below zoom
    text_label = plate_text if plate_text else ""
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, new_w / 220)
    thickness = max(1, int(font_scale * 2))
    (tw, th), baseline = cv2.getTextSize(text_label, font, font_scale, thickness) if text_label else ((0, 0), 0)
    text_h = th + baseline + 8 if text_label else 0

    border = 2
    fh, fw = frame.shape[:2]
    x0, y0 = 10, 10
    x1 = x0 + new_w + border * 2
    y1 = y0 + target_h + border * 2 + text_h
    if x1 > fw or y1 > fh:
        return frame

    out = frame.copy()
    # White background for the entire block (image + text strip)
    out[y0:y1, x0:x1] = (255, 255, 255)
    # Paste zoomed plate
    out[y0 + border:y0 + border + target_h, x0 + border:x0 + border + new_w] = zoomed
    # Render plate text in the strip below
    if text_label:
        txt_x = x0 + max(0, (new_w + border * 2 - tw) // 2)
        txt_y = y0 + border + target_h + th + 4
        cv2.putText(out, text_label, (txt_x, txt_y), font, font_scale, (20, 20, 180), thickness, cv2.LINE_AA)
    return out


def _apply_watermark(frame: np.ndarray) -> np.ndarray:
    """Burn a semi-transparent 'Parking Enforcement' watermark into the bottom-right corner."""
    label = "שוטר חניה | Parking Enforcement"
    font      = cv2.FONT_HERSHEY_SIMPLEX
    h, w      = frame.shape[:2]
    scale     = max(0.35, w / 2200)
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
    pad = 6
    x = w - tw - pad - 4
    y = h - pad
    # Semi-transparent dark rectangle
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - pad, y - th - pad), (x + tw + pad, y + baseline + pad), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
    cv2.putText(frame, label, (x, y), font, scale, (200, 200, 200), thickness, cv2.LINE_AA)
    return frame


def _find_best_plate_box(
    cap: cv2.VideoCapture,
    sample_count: int = 30,
    curb_box: Optional[BBox] = None,
) -> Optional[BBox]:
    """Pre-scan sampled frames to find the highest-scoring plate box.
    Resets capture position to 0 when done.
    """
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return None
    step = max(1, total_frames // sample_count)
    best_box: Optional[BBox] = None
    best_area = 0
    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        box = detect_plate_near_curb(frame, curb_box)
        if box is None:
            continue
        area = box[2] * box[3]
        if area > best_area:
            best_area = area
            best_box = box
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return best_box


def _deskew_plate(crop: np.ndarray) -> np.ndarray:
    """Apply perspective correction: find the minimum-area bounding rect of
    the plate content and warp it to a canonical upright rectangle.
    Falls back to the original crop if the angle is small (<5°) or detection fails.
    """
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return crop
        all_pts = np.vstack(contours)
        rect = cv2.minAreaRect(all_pts)
        angle = rect[2]
        # minAreaRect returns angle in (-90, 0]; adjust to (-45, 45]
        if angle < -45:
            angle += 90
        if abs(angle) < 1.0:
            return crop  # no meaningful skew
        h, w = crop.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rotated = cv2.warpAffine(crop, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    except Exception:
        return crop


def _prepare_plate_crop(frame: np.ndarray, plate_box: BBox, target_width: int = 400) -> Optional[np.ndarray]:
    """Crop to plate region, deskew, pad, 6× upscale (test-engine approach),
    apply bilateral filter + equalizeHist + OTSU.
    Returns grayscale binary image ready for Tesseract, or None on failure.
    """
    x, y, w, h = plate_box
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(frame.shape[1], x + w)
    y2 = min(frame.shape[0], y + h)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 10:
        return None

    # Perspective deskew
    crop = _deskew_plate(crop)

    # Add padding so characters at plate edges aren't clipped
    pad = max(4, crop.shape[0] // 8)
    crop = cv2.copyMakeBorder(crop, pad, pad, pad, pad, cv2.BORDER_REPLICATE)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop

    # 6× upscale (test engine value) — better than targeting a fixed width for small plates
    gray = cv2.resize(gray, None, fx=6.0, fy=6.0, interpolation=cv2.INTER_CUBIC)

    # Bilateral filter: preserves character edges while smoothing noise
    gray = cv2.bilateralFilter(gray, 9, 50, 50)

    # Histogram equalisation for contrast normalisation
    gray = cv2.equalizeHist(gray)

    # OTSU thresholding
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _prepare_plate_crop_adaptive(frame: np.ndarray, plate_box: BBox, target_width: int = 400) -> Optional[np.ndarray]:
    """Same as _prepare_plate_crop but uses adaptive thresholding instead of OTSU.
    Better for plates with uneven lighting or shadows.
    """
    x, y, w, h = plate_box
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(frame.shape[1], x + w)
    y2 = min(frame.shape[0], y + h)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 10:
        return None

    crop = _deskew_plate(crop)
    pad = max(4, crop.shape[0] // 8)
    crop = cv2.copyMakeBorder(crop, pad, pad, pad, pad, cv2.BORDER_REPLICATE)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    gray = cv2.resize(gray, None, fx=6.0, fy=6.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 50, 50)
    gray = cv2.equalizeHist(gray)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    return binary


# Character substitutions for OCR (from test engine)
_OCR_CHAR_SUBS = str.maketrans({"O": "0", "Q": "0", "D": "0",
                                 "I": "1", "L": "1",
                                 "Z": "2",
                                 "S": "5",
                                 "B": "8"})


def _clean_ocr_text(text: str) -> str:
    """Apply character substitutions then keep digits only.
    O→0, Q→0, D→0, I→1, L→1, Z→2, S→5, B→8 (from test engine).
    """
    return re.sub(r"[^0-9]", "", text.upper().translate(_OCR_CHAR_SUBS))


def _run_tesseract(img: np.ndarray, psm: int = 7) -> str:
    """Run Tesseract with the given PSM mode; return digits-only string."""
    # oem 1 = LSTM only (more accurate on small/blurry text than oem 3)
    text = pytesseract.image_to_string(
        img,
        config=f"--oem 1 --psm {psm} -c tessedit_char_whitelist=0123456789",
    )
    return _clean_ocr_text(text or "")


def _ocr_plate_image(binary: np.ndarray, adaptive: Optional[np.ndarray] = None) -> str:
    """Try multiple PSM modes, both polarities, and both preprocessing variants; return best digit string."""
    best = ""
    images = [binary, cv2.bitwise_not(binary)]
    if adaptive is not None:
        images += [adaptive, cv2.bitwise_not(adaptive)]
    # PSM 7 = single line, PSM 8 = single word, PSM 6 = uniform block, PSM 13 = raw line
    for psm in (7, 8, 6, 13):
        for img in images:
            digits = _run_tesseract(img, psm=psm)
            if 7 <= len(digits) <= 8:
                return digits          # first confident hit
            if len(digits) > len(best):
                best = digits
    return best


def _ocr_frame(frame: np.ndarray) -> Tuple[str, Optional[str]]:
    """Detect plate region, crop, preprocess, then OCR with multi-PSM voting."""
    plate_box = detect_plate_box(frame)
    if plate_box is None:
        return ("11111", "Plate not detected in frame")

    binary = _prepare_plate_crop(frame, plate_box, target_width=600)
    if binary is None:
        return ("11111", "Empty plate crop")

    adaptive = _prepare_plate_crop_adaptive(frame, plate_box, target_width=600)
    digits = _ocr_plate_image(binary, adaptive)
    if 7 <= len(digits) <= 8:
        return (digits, None)

    return ("11111", "OCR could not read valid 7-8 digit plate")


def extract_license_plate(
    video_bytes: Optional[bytes] = None,
    frame_jpeg: Optional[bytes] = None,
    use_fast_hsv: bool = False,
    registry_lookup=None,
) -> Tuple[str, Optional[str]]:
    """OCR on original (unblurred) frames.
    Tries PaddleOCR + YOLO pipeline first; falls back to Tesseract.
    frame_jpeg is ignored — always use original video_bytes to avoid blurred output.
    """
    if not video_bytes:
        return ("11111", "No video provided for OCR")

    # ── Try PaddleOCR + YOLO pipeline ──────────────────────────────────────
    try:
        from app.services.anpr_pipeline import extract_plate_from_bytes, is_paddle_available
        if is_paddle_available():
            plate, reason = extract_plate_from_bytes(video_bytes)
            if plate != "11111":
                return plate, reason
            # paddle ran but found nothing — fall through to Tesseract
    except Exception as _paddle_err:
        print(f"[OCR] ANPR pipeline error (non-fatal): {_paddle_err}", flush=True)

    if pytesseract is None:
        return ("11111", "Tesseract is not installed")

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name
    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return ("11111", "Could not open video for OCR")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sample_count = 30
        step = max(1, total // sample_count) if total > 0 else 1
        last_reason = "No frames decoded"

        from collections import Counter, deque
        # Rolling window of 20 readings (test engine approach)
        vote_window: deque = deque(maxlen=20)
        prev_box: Optional[BBox] = None  # for IoU continuity bonus

        for i in range(0, max(total, 1), step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = cap.read()
            if not ok:
                continue

            # Sharpness gate — skip blurry frames (test engine: threshold=10)
            gray_f = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if float(cv2.Laplacian(gray_f, cv2.CV_64F).var()) < 10:
                continue

            plate_box = detect_plate_box(frame, prev_box=prev_box)
            if plate_box is None:
                last_reason = "Plate not detected in frame"
                continue
            prev_box = plate_box

            binary = _prepare_plate_crop(frame, plate_box)
            if binary is None:
                last_reason = "Empty plate crop"
                continue
            adaptive = _prepare_plate_crop_adaptive(frame, plate_box)
            digits = _ocr_plate_image(binary, adaptive)
            if 7 <= len(digits) <= 8:
                vote_window.append(digits)
            else:
                last_reason = "OCR could not read valid 7-8 digit plate"

        cap.release()

        if vote_window:
            votes = Counter(vote_window)
            best_plate, count = votes.most_common(1)[0]
            total_votes = sum(votes.values())

            # Position-consensus when all tied at 1 vote
            if count == 1 and total_votes >= 3:
                candidates = [p for p in votes if len(p) in (7, 8)]
                if candidates:
                    common_len = Counter(len(p) for p in candidates).most_common(1)[0][0]
                    same_len = [p for p in candidates if len(p) == common_len]
                    if same_len:
                        consensus = "".join(
                            Counter(p[i] for p in same_len).most_common(1)[0][0]
                            for i in range(common_len)
                        )
                        best_plate = consensus
                        print(f"[OCR] No majority — position consensus: {consensus}")

            print(f"[OCR] Votes: {dict(votes.most_common(5))} → {best_plate} ({count}/{total_votes})")
            return (best_plate, None)

        return ("11111", last_reason)
    finally:
        Path(input_path).unlink(missing_ok=True)


def process_video(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
) -> Tuple[bytes, bytes]:
    """Build processed review video: detect plate near red/white curb,
    blur everything except the plate region.
    """
    kernel = _normalize_kernel(blur_strength or BLUR_KERNEL)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("OpenCV could not open video; refusing unsafe fallback")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)  or 0)
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)  or 1)

    if width <= 0 or height <= 0:
        cap.release()
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("Could not read video dimensions")

    # Use MP4+mp4v for the intermediate file
    temp_out = tempfile.mktemp(suffix=".mp4")
    writer = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        # fallback: try AVI+XVID
        temp_out = tempfile.mktemp(suffix=".avi")
        writer = cv2.VideoWriter(
            temp_out,
            cv2.VideoWriter_fourcc(*"XVID"),
            fps,
            (width, height),
        )
    if not writer.isOpened():
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("cv2.VideoWriter failed to open with mp4v and XVID codecs")

    # Step 1: find the red/white curb in the first readable frames.
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    curb_box: Optional[BBox] = None
    for _probe in range(min(10, total_frames)):
        ret_p, probe_frame = cap.read()
        if ret_p:
            curb_box = detect_redwhite_curb(probe_frame)
            if curb_box is not None:
                break

    # Step 2: pre-scan to find best plate near that curb; seed tracker.
    global_best = _find_best_plate_box(cap, sample_count=30, curb_box=curb_box)
    tracker = PlateTracker()
    if global_best is not None:
        tracker.last_box = global_best

    # Step 2b: OCR the best plate crop once so we can burn the number onto the video.
    plate_overlay_text: Optional[str] = None
    if global_best is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        _ok, _f = cap.read()
        if _ok:
            x, y, w, h = global_best
            _crop = _f[max(0,y):min(_f.shape[0],y+h), max(0,x):min(_f.shape[1],x+w)]
            _txt = _quick_ocr_plate_crop(_crop)
            if _txt:
                plate_overlay_text = _txt
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    frame_index   = 0
    preview_frame = None
    preview_index = int(total_frames * extract_frame_at)
    last_effective_plate: Optional[BBox] = global_best

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Run detection every 3rd frame; reuse last known plate for intermediate frames
        if frame_index % 3 == 0:
            plate = detect_plate_near_curb(frame, curb_box)
            tracked_plate = tracker.update(plate)
            effective_plate = tracked_plate if tracked_plate is not None else global_best
            if effective_plate is None:
                effective_plate = detect_plate_box(frame)
            last_effective_plate = effective_plate
        else:
            last_effective_plate = tracker.update(None)
            if last_effective_plate is None:
                last_effective_plate = global_best
        output = _blur_everything_except_plate(frame, last_effective_plate, kernel)
        if last_effective_plate is not None:
            output = _overlay_plate_magnified(output, last_effective_plate, original_frame=frame, plate_text=plate_overlay_text)
        output = _apply_watermark(output)
        writer.write(output)
        if frame_index == preview_index:
            preview_frame = output.copy()
        frame_index += 1

    cap.release()
    writer.release()

    if frame_index == 0:
        Path(temp_out).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("No frames decoded; refusing unsafe fallback")

    temp_size = Path(temp_out).stat().st_size if Path(temp_out).exists() else 0
    if temp_size < 1024:
        Path(temp_out).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError(f"Intermediate video file too small ({temp_size} bytes) — writer may have failed silently")

    ffmpeg    = get_ffmpeg()
    final_out = tempfile.mktemp(suffix=".mp4")
    try:
        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-i", temp_out,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "26",
                # Cap at 1280×720 (720p) to preserve plate detail; two-step ensures even dimensions
                "-vf", "scale=min(1280\\,iw):min(720\\,ih):force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-threads", "4",
                "-an",
                final_out,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            err_msg = result.stderr.decode(errors="replace")[-800:]
            raise RuntimeError(f"ffmpeg failed (code {result.returncode}): {err_msg}")
        processed_video = Path(final_out).read_bytes()
    finally:
        Path(temp_out).unlink(missing_ok=True)
        Path(final_out).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)

    preview_jpeg = b""
    if preview_frame is not None:
        ok, buf = cv2.imencode(".jpg", preview_frame)
        if ok:
            preview_jpeg = buf.tobytes()

    return processed_video, preview_jpeg


def _burn_timestamp(frame: np.ndarray, label: str) -> np.ndarray:
    """Burn a timestamp string into the bottom-left of a frame."""
    h, w = frame.shape[:2]
    font       = cv2.FONT_HERSHEY_SIMPLEX
    scale      = max(0.5, w / 1280)
    thickness  = max(1, int(scale * 2))
    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
    x = 10
    y = h - 10
    # Dark semi-transparent background behind text
    pad = 4
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - pad, y - th - pad), (x + tw + pad, y + baseline + pad), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, label, (x, y), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return frame


def extract_frames(
    video_bytes: bytes,
    count: int = 5,
    base_time=None,  # datetime object (captured_at); if provided, timestamps are burned in
) -> list:
    """Extract `count` evenly-spaced frames from a video (blurred or otherwise).
    Returns list of (jpeg_bytes: bytes, frame_time_sec: float).
    If base_time is given, each frame gets the real-world timestamp burned in.
    """
    from datetime import timedelta
    results = []
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name
    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return results
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        if total <= 0 or count <= 0:
            cap.release()
            return results
        # Pick evenly-spaced frame indices, avoiding very first and very last frame
        step = max(1, total // (count + 1))
        indices = [step * (i + 1) for i in range(count) if step * (i + 1) < total]
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            frame_sec = round(idx / fps, 2)
            if base_time is not None:
                try:
                    ts = base_time + timedelta(seconds=frame_sec)
                    label = ts.strftime("%d/%m/%Y %H:%M:%S")
                except Exception:
                    label = f"+{frame_sec:.1f}s"
            else:
                label = f"+{frame_sec:.1f}s"
            frame = _burn_timestamp(frame, label)
            frame = _apply_watermark(frame)
            ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok2:
                results.append((buf.tobytes(), frame_sec))
        cap.release()
    finally:
        Path(input_path).unlink(missing_ok=True)
    return results


def process_video_fast_hsv(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
):
    """Process video: detect plate (YOLO vehicle + HSV/YOLO plate), blur everything except plate."""
    return _process_video_with_yolo(
        video_bytes=video_bytes,
        blur_strength=blur_strength,
        extract_frame_at=extract_frame_at,
    )


def _process_video_with_yolo(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
) -> Tuple[bytes, bytes]:
    """process_video variant that uses YOLO vehicle tracking to narrow down plate ROI.
    Falls back to full-frame HSV detection when YOLO is unavailable.
    """
    kernel = _normalize_kernel(blur_strength or BLUR_KERNEL)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("OpenCV could not open video; refusing unsafe fallback")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)  or 0)
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)  or 1)

    if width <= 0 or height <= 0:
        cap.release()
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("Could not read video dimensions")

    temp_out = tempfile.mktemp(suffix=".mp4")
    writer = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        temp_out = tempfile.mktemp(suffix=".avi")
        writer = cv2.VideoWriter(
            temp_out,
            cv2.VideoWriter_fourcc(*"XVID"),
            fps,
            (width, height),
        )
    if not writer.isOpened():
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("cv2.VideoWriter failed to open with mp4v and XVID codecs")

    try:
        from app.services.anpr_pipeline import detect_and_track_vehicles, detect_plate_in_frame as _anpr_detect
        _use_yolo = True
    except Exception:
        _use_yolo = False
        _anpr_detect = None

    # Pre-scan: find best plate box using YOLO-guided or full-frame HSV
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    curb_box: Optional[BBox] = None
    for _probe in range(min(10, total_frames)):
        ret_p, probe_frame = cap.read()
        if ret_p:
            curb_box = detect_redwhite_curb(probe_frame)
            if curb_box is not None:
                break

    global_best = _find_best_plate_box(cap, sample_count=30, curb_box=curb_box)
    tracker = PlateTracker()
    if global_best is not None:
        tracker.last_box = global_best

    # OCR the best plate crop once so we can burn the number onto every frame.
    plate_overlay_text: Optional[str] = None
    if global_best is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        _ok, _f = cap.read()
        if _ok:
            x, y, w, h = global_best
            _crop = _f[max(0,y):min(_f.shape[0],y+h), max(0,x):min(_f.shape[1],x+w)]
            _txt = _quick_ocr_plate_crop(_crop)
            if _txt:
                plate_overlay_text = _txt

    frame_index   = 0
    preview_frame = None
    preview_index = int(total_frames * extract_frame_at)
    last_effective_plate: Optional[BBox] = global_best
    last_vehicle_roi: Optional[tuple] = None  # x1,y1,x2,y2

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_index % 3 == 0:
            # Get vehicle ROI from YOLO (when available)
            vehicle_roi_xyxy = None
            if _use_yolo:
                vehicles = detect_and_track_vehicles(frame)
                if vehicles:
                    # Use the largest vehicle
                    best_v = max(vehicles, key=lambda v: (v["bbox"][2]-v["bbox"][0])*(v["bbox"][3]-v["bbox"][1]))
                    vx1, vy1, vx2, vy2 = best_v["bbox"]
                    h_car = vy2 - vy1
                    # Plates are in lower 60% of vehicle
                    vehicle_roi_xyxy = (vx1, vy1 + int(h_car * 0.40), vx2, vy2)
                    last_vehicle_roi = vehicle_roi_xyxy

            # Plate detection: YOLO/HSV within vehicle ROI, then curb-guided, then full-frame
            if vehicle_roi_xyxy and _anpr_detect:
                plate = _anpr_detect(frame, vehicle_roi_xyxy)
            else:
                plate = detect_plate_near_curb(frame, curb_box)

            tracked_plate = tracker.update(plate)
            effective_plate = tracked_plate if tracked_plate is not None else global_best
            if effective_plate is None:
                effective_plate = detect_plate_box(frame)
            last_effective_plate = effective_plate
        else:
            last_effective_plate = tracker.update(None)
            if last_effective_plate is None:
                last_effective_plate = global_best

        output = _blur_everything_except_plate(frame, last_effective_plate, kernel)
        if last_effective_plate is not None:
            output = _overlay_plate_magnified(output, last_effective_plate, original_frame=frame, plate_text=plate_overlay_text)
        output = _apply_watermark(output)
        writer.write(output)
        if frame_index == preview_index:
            preview_frame = output.copy()
        frame_index += 1

    cap.release()
    writer.release()

    if frame_index == 0:
        Path(temp_out).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("No frames decoded; refusing unsafe fallback")

    temp_size = Path(temp_out).stat().st_size if Path(temp_out).exists() else 0
    if temp_size < 1024:
        Path(temp_out).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError(f"Intermediate video file too small ({temp_size} bytes)")

    ffmpeg    = get_ffmpeg()
    final_out = tempfile.mktemp(suffix=".mp4")
    try:
        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-i", temp_out,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "26",
                "-vf", "scale=min(1280\\,iw):min(720\\,ih):force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-threads", "4",
                "-an",
                final_out,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            err_msg = result.stderr.decode(errors="replace")[-800:]
            raise RuntimeError(f"ffmpeg failed (code {result.returncode}): {err_msg}")
        processed_video = Path(final_out).read_bytes()
    finally:
        Path(temp_out).unlink(missing_ok=True)
        Path(final_out).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)

    preview_jpeg = b""
    if preview_frame is not None:
        ok, buf = cv2.imencode(".jpg", preview_frame)
        if ok:
            preview_jpeg = buf.tobytes()

    return processed_video, preview_jpeg


def process_video_with_violation_pipeline(
    video_bytes: bytes,
    output_dir: Optional[str] = None,
    extract_frame_at: float = 0.5,
    blur_kernel_size: Optional[int] = None,
):
    # OCR first on the original unblurred video, then blur.
    best_plate, _ = extract_license_plate(video_bytes=video_bytes)
    processed_video_bytes, ticket_frame_jpeg = process_video(
        video_bytes=video_bytes,
        blur_strength=int(blur_kernel_size or BLUR_KERNEL),
        extract_frame_at=extract_frame_at,
    )
    return processed_video_bytes, ticket_frame_jpeg, best_plate
