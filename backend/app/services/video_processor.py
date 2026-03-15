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


BLUR_KERNEL = 35
TRACK_MISSES = 10
SMOOTH_ALPHA = 0.70

HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)

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


def detect_plate_box(frame: np.ndarray) -> Optional[BBox]:
    """Detect yellow license plate in frame; returns best bounding box or None."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array(HSV_LOWER_YELLOW, dtype=np.uint8),
        np.array(HSV_UPPER_YELLOW, dtype=np.uint8),
    )
    kernel_open  = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel_open)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best: Optional[BBox] = None
    best_score = 0.0
    h_frame = frame.shape[0]
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 40 or h < 12:
            continue
        ratio = w / float(h) if h > 0 else 0.0
        if ratio < 2.0 or ratio > 7.0:
            continue
        area = w * h
        lower_half_bonus = 1.0 + (y / max(1, h_frame))
        score = area * lower_half_bonus
        if score > best_score:
            best_score = score
            best = (x, y, w, h)
    return best


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


def detect_plate_near_curb(frame: np.ndarray, curb_box: Optional[BBox]) -> Optional[BBox]:
    """Find yellow plate on the car parked next to the curb.

    Searches the region above/around the curb first; falls back to
    full-frame search when nothing is found there.
    """
    h_frame, w_frame = frame.shape[:2]
    if curb_box is not None:
        cx, cy, cw, ch = curb_box
        sy1 = max(0, cy - int(h_frame * 0.70))
        sy2 = min(h_frame, cy + ch + int(h_frame * 0.05))
        sx1 = max(0, cx - int(cw * 0.20))
        sx2 = min(w_frame, cx + cw + int(cw * 0.20))
        region = frame[sy1:sy2, sx1:sx2]
        box = detect_plate_box(region)
        if box is not None:
            bx, by, bw, bh = box
            return (sx1 + bx, sy1 + by, bw, bh)
    return detect_plate_box(frame)


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
    When no plate box is found, the entire frame stays blurred.
    """
    blurred = cv2.GaussianBlur(frame, (kernel, kernel), 0)
    if plate_box is None:
        return blurred
    x, y, w, h = _expand_box(plate_box, frame.shape, ratio=0.5)
    if w <= 0 or h <= 0:
        return blurred
    blurred[y:y + h, x:x + w] = frame[y:y + h, x:x + w].copy()
    return blurred


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


def extract_license_plate(
    video_bytes: Optional[bytes] = None,
    frame_jpeg: Optional[bytes] = None,
    use_fast_hsv: bool = False,
    registry_lookup=None,
) -> Tuple[str, Optional[str]]:
    """Compatibility OCR helper for worker imports."""
    if pytesseract is None:
        return ("11111", "Tesseract is not installed")
    frame: Optional[np.ndarray] = None
    if frame_jpeg:
        arr = np.frombuffer(frame_jpeg, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None and video_bytes:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(video_bytes)
            input_path = f.name
        try:
            cap = cv2.VideoCapture(input_path)
            ok, candidate = cap.read()
            cap.release()
            if ok:
                frame = candidate
        finally:
            Path(input_path).unlink(missing_ok=True)
    if frame is None:
        return ("11111", "No image frame available for OCR")
    plate_box = detect_plate_box(frame)
    if plate_box is None:
        return ("11111", "Plate not detected")
    x, y, w, h = _expand_box(plate_box, frame.shape, ratio=0.2)
    crop = frame[y:y + h, x:x + w]
    if crop.size == 0:
        return ("11111", "Empty plate crop")
    crop = _safe_denoise_and_sharpen(crop)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(
        gray,
        config="--psm 7 -c tessedit_char_whitelist=0123456789",
    )
    digits = re.sub(r"[^0-9]", "", text or "")
    if 7 <= len(digits) <= 8:
        return (digits, None)
    return ("11111", "OCR could not read valid 7-8 digit plate")


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

    temp_out = tempfile.mktemp(suffix=".mp4")
    writer = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

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

    frame_index   = 0
    preview_frame = None
    preview_index = int(total_frames * extract_frame_at)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        plate        = detect_plate_near_curb(frame, curb_box)
        tracked_plate = tracker.update(plate)
        output = _blur_everything_except_plate(frame, tracked_plate, kernel)
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

    ffmpeg    = get_ffmpeg()
    final_out = tempfile.mktemp(suffix=".mp4")
    try:
        subprocess.run(
            [
                ffmpeg, "-y",
                "-i", temp_out,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                final_out,
            ],
            check=True,
            capture_output=True,
        )
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


def process_video_fast_hsv(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
):
    return process_video(
        video_bytes=video_bytes,
        blur_strength=blur_strength,
        extract_frame_at=extract_frame_at,
    )


def process_video_with_violation_pipeline(
    video_bytes: bytes,
    output_dir: Optional[str] = None,
    extract_frame_at: float = 0.5,
    blur_kernel_size: Optional[int] = None,
):
    processed_video_bytes, ticket_frame_jpeg = process_video(
        video_bytes=video_bytes,
        blur_strength=int(blur_kernel_size or BLUR_KERNEL),
        extract_frame_at=extract_frame_at,
    )
    best_plate, _ = extract_license_plate(
        video_bytes=video_bytes,
        frame_jpeg=ticket_frame_jpeg,
        use_fast_hsv=True,
    )
    return processed_video_bytes, ticket_frame_jpeg, best_plate
