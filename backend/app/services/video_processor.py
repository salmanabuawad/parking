from __future__ import annotations

import json
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

try:
    import pytesseract
except Exception:
    pytesseract = None


# ------------------------------------------------------------------
# Configuration defaults
# ------------------------------------------------------------------

BLUR_KERNEL = 35
TRACK_MISSES = 8
SMOOTH_ALPHA = 0.65

HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)

BBox = Tuple[int, int, int, int]


# ------------------------------------------------------------------
# Tracker
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def normalize_kernel(k: int) -> int:
    if k < 3:
        k = BLUR_KERNEL
    if k % 2 == 0:
        k += 1
    return k


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
            [ffprobe, "-v", "quiet", "-show_format", "-show_streams", "-print_format", "json", input_path],
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


# ------------------------------------------------------------------
# Plate detection / OCR compatibility
# ------------------------------------------------------------------

def detect_plate_box(frame: np.ndarray) -> Optional[BBox]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(
        hsv,
        np.array(HSV_LOWER_YELLOW, dtype=np.uint8),
        np.array(HSV_UPPER_YELLOW, dtype=np.uint8),
    )

    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best: Optional[BBox] = None
    best_area = 0

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)

        if w < 40 or h < 12:
            continue

        ratio = w / float(h) if h > 0 else 0.0
        if ratio < 2.0 or ratio > 7.0:
            continue

        area = w * h
        if area > best_area:
            best_area = area
            best = (x, y, w, h)

    return best


def _safe_denoise_and_sharpen(img: np.ndarray) -> np.ndarray:
    try:
        denoised = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)
    except Exception:
        denoised = img
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
    return cv2.filter2D(denoised, -1, kernel)


def extract_license_plate(
    video_bytes: Optional[bytes] = None,
    frame_jpeg: Optional[bytes] = None,
    use_fast_hsv: bool = False,
    registry_lookup=None,
) -> Tuple[str, Optional[str]]:
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

    x, y, w, h = plate_box
    pad_w = int(w * 0.2)
    pad_h = int(h * 0.2)
    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(frame.shape[1], x + w + pad_w)
    y2 = min(frame.shape[0], y + h + pad_h)

    crop = frame[y1:y2, x1:x2]
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


# ------------------------------------------------------------------
# Inverse blur logic
# ------------------------------------------------------------------

def expand_box(box: BBox, frame_shape: Tuple[int, int, int], ratio: float = 0.75) -> BBox:
    x, y, w, h = box
    dw = int(w * ratio)
    dh = int(h * ratio)

    x1 = max(0, x - dw)
    y1 = max(0, y - dh)
    x2 = min(frame_shape[1], x + w + dw)
    y2 = min(frame_shape[0], y + h + dh)

    return x1, y1, x2 - x1, y2 - y1


def blur_everything_except_plate(
    frame: np.ndarray,
    plate_box: Optional[BBox],
    kernel: int,
) -> np.ndarray:
    """
    Blur all of the frame except the detected/tracked plate.
    If no plate exists, keep the frame unchanged so we never blur the plate by mistake.
    """
    if plate_box is None:
        return frame.copy()

    blurred = cv2.GaussianBlur(frame, (kernel, kernel), 0)
    x, y, w, h = expand_box(plate_box, frame.shape, ratio=0.75)

    if w <= 0 or h <= 0:
        return frame.copy()

    roi = frame[y:y + h, x:x + w].copy()
    blurred[y:y + h, x:x + w] = roi
    return blurred


# ------------------------------------------------------------------
# Main processor
# ------------------------------------------------------------------

def process_video(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
) -> Tuple[bytes, bytes]:
    """
    Review-video processor:
    - detect plate
    - track plate across short misses
    - blur everything except the plate
    - blur strength comes from caller config
    """
    kernel = normalize_kernel(blur_strength or BLUR_KERNEL)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("OpenCV could not open video; refusing unsafe fallback")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)

    if width <= 0 or height <= 0:
        cap.release()
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("Could not read video dimensions")

    raw_out_path = tempfile.mktemp(suffix=".mp4")
    writer = cv2.VideoWriter(
        raw_out_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    tracker = PlateTracker()

    frame_index = 0
    preview_frame = None
    preview_index = int(total_frames * extract_frame_at)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_plate = detect_plate_box(frame)
        tracked_plate = tracker.update(current_plate)

        output = blur_everything_except_plate(frame, tracked_plate, kernel)
        writer.write(output)

        if frame_index == preview_index:
            preview_frame = output.copy()

        frame_index += 1

    cap.release()
    writer.release()

    if frame_index == 0:
        Path(raw_out_path).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)
        raise RuntimeError("No frames decoded; refusing unsafe fallback")

    ffmpeg = get_ffmpeg()
    final_out_path = tempfile.mktemp(suffix=".mp4")

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                raw_out_path,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                final_out_path,
            ],
            check=True,
            capture_output=True,
        )
        video_data = Path(final_out_path).read_bytes()
    finally:
        Path(raw_out_path).unlink(missing_ok=True)
        Path(final_out_path).unlink(missing_ok=True)
        Path(input_path).unlink(missing_ok=True)

    jpeg = b""
    if preview_frame is not None:
        ok, buf = cv2.imencode(".jpg", preview_frame)
        if ok:
            jpeg = buf.tobytes()

    return video_data, jpeg


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
