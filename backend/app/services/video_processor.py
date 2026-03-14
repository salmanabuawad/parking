
from __future__ import annotations

import re
import cv2
import numpy as np
import tempfile
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional, Tuple

DEFAULT_BLUR = 35
TRACK_MISSES = 8
SMOOTH_ALPHA = 0.65

HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)

BBox = Tuple[int, int, int, int]


@dataclass
class PlateTracker:
    max_misses: int = TRACK_MISSES
    alpha: float = SMOOTH_ALPHA

    def __post_init__(self):
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


def detect_plate_box(frame: np.ndarray) -> Optional[BBox]:

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(
        hsv,
        np.array(HSV_LOWER_YELLOW, dtype=np.uint8),
        np.array(HSV_UPPER_YELLOW, dtype=np.uint8),
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_box = None
    best_area = 0

    for c in contours:

        x,y,w,h = cv2.boundingRect(c)

        if w < 40 or h < 15:
            continue

        ratio = w / float(h)

        if ratio < 2 or ratio > 7:
            continue

        area = w*h

        if area > best_area:
            best_area = area
            best_box = (x,y,w,h)

    return best_box


def normalize_kernel(k: int):

    if k < 3:
        k = DEFAULT_BLUR

    if k % 2 == 0:
        k += 1

    return k


def expand_box(box: BBox, frame_shape, ratio=0.5):

    x,y,w,h = box

    dw = int(w * ratio)
    dh = int(h * ratio)

    x1 = max(0, x - dw)
    y1 = max(0, y - dh)

    x2 = min(frame_shape[1], x + w + dw)
    y2 = min(frame_shape[0], y + h + dh)

    return x1, y1, x2-x1, y2-y1


def blur_everything_except_plate(frame, plate_box, kernel):

    if plate_box is None:
        return frame.copy()

    blurred = cv2.GaussianBlur(frame, (kernel,kernel), 0)

    x,y,w,h = expand_box(plate_box, frame.shape)

    blurred[y:y+h, x:x+w] = frame[y:y+h, x:x+w]

    return blurred


def get_ffmpeg():

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        ff = shutil.which("ffmpeg")
        if ff:
            return ff

    raise RuntimeError("ffmpeg not found")


def process_video(video_bytes: bytes, blur_strength: int = DEFAULT_BLUR):

    kernel = normalize_kernel(blur_strength)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    cap = cv2.VideoCapture(input_path)

    if not cap.isOpened():
        raise RuntimeError("Cannot open video")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    temp_out = tempfile.mktemp(suffix=".mp4")

    writer = cv2.VideoWriter(
        temp_out,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width,height)
    )

    tracker = PlateTracker()
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
    preview_index = min(total_frames - 1, max(0, int(total_frames * 0.5)))
    frame_index = 0
    preview_frame = None

    while True:

        ret, frame = cap.read()
        if not ret:
            break

        plate = detect_plate_box(frame)

        tracked = tracker.update(plate)

        output = blur_everything_except_plate(frame, tracked, kernel)

        writer.write(output)

        if frame_index == preview_index:
            preview_frame = output.copy()
        frame_index += 1

    cap.release()
    writer.release()

    ffmpeg = get_ffmpeg()

    final_path = tempfile.mktemp(suffix=".mp4")

    subprocess.run([
        ffmpeg,
        "-y",
        "-i", temp_out,
        "-c:v","libx264",
        "-pix_fmt","yuv420p",
        "-movflags","+faststart",
        "-an",
        final_path
    ], check=True)

    video = Path(final_path).read_bytes()

    jpeg = b""
    if preview_frame is not None:
        ok, buf = cv2.imencode(".jpg", preview_frame)
        if ok:
            jpeg = buf.tobytes()

    Path(temp_out).unlink(missing_ok=True)
    Path(final_path).unlink(missing_ok=True)
    Path(input_path).unlink(missing_ok=True)

    return video, jpeg


def process_video_fast_hsv(video_bytes: bytes, blur_strength: int = DEFAULT_BLUR, **kwargs):
    return process_video(video_bytes, blur_strength)


def process_video_with_violation_pipeline(
    video_bytes: bytes,
    output_dir: Optional[str] = None,
    extract_frame_at: float = 0.5,
    blur_kernel_size: Optional[int] = None,
    **kwargs,
):
    processed, ticket_jpeg = process_video(video_bytes, blur_kernel_size or DEFAULT_BLUR)
    return processed, ticket_jpeg, "11111"


def extract_license_plate(
    *,
    frame_jpeg: Optional[bytes] = None,
    video_bytes: Optional[bytes] = None,
    use_fast_hsv: bool = False,
    registry_lookup: Any = None,
) -> Tuple[str, Optional[str]]:
    """Extract license plate from a ticket frame (or a frame from video). Returns (plate_str, reason_or_None). Use '11111' when not detected."""
    frame: Optional[np.ndarray] = None
    if frame_jpeg:
        arr = np.frombuffer(frame_jpeg, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    elif video_bytes:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        try:
            tmp.write(video_bytes)
            tmp.close()
            cap = cv2.VideoCapture(tmp.name)
            if cap.isOpened():
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                mid = min(total - 1, max(0, int(total * 0.5)))
                cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
                ret, frame = cap.read()
                if not ret:
                    frame = None
            cap.release()
        finally:
            Path(tmp.name).unlink(missing_ok=True)
    if frame is None:
        return "11111", "No frame available"

    try:
        from app.plate_pipeline.ocr_reader import read_plate_crop
    except ImportError:
        return "11111", "OCR module not available"

    try:
        box = detect_plate_box(frame)
        if not box:
            return "11111", "No plate region detected"
        x, y, w, h = expand_box(box, frame.shape, 0.2)
        crop = frame[y : y + h, x : x + w]
        if crop.size == 0:
            return "11111", "Plate crop empty"
        digits, err = read_plate_crop(crop)
        cleaned = re.sub(r"[^A-Za-z0-9]", "", (digits or "").strip())
        if len(cleaned) < 5 or len(cleaned) > 12:
            return "11111", (err or "OCR returned no valid plate")
        plate = cleaned.upper()
        if registry_lookup is not None and hasattr(registry_lookup, "plate_exists") and not registry_lookup.plate_exists(plate):
            return "11111", "Plate not in registry"
        return plate, None
    except Exception as e:
        return "11111", str(e)


def extract_video_params(path: str) -> Optional[dict]:
    """Extract fps, width, height, duration_sec from a video file. Returns None on failure."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if w <= 0 or h <= 0:
            return None
        duration_sec = (n / fps) if n and fps else 0.0
        return {"fps": round(fps, 2), "width": w, "height": h, "duration_sec": round(duration_sec, 2)}
    finally:
        cap.release()
