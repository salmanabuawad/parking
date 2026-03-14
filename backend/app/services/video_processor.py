from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

BLUR_KERNEL = 35
TRACK_MISSES = 8
SMOOTH_ALPHA = 0.65

HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)

BBox = Tuple[int, int, int, int]


@dataclass
class PlateTracker:
    max_misses: int = TRACK_MISSES
    alpha: float = SMOOTH_ALPHA

    def __post_init__(self) -> None:
        self.last_box: Optional[BBox] = None
        self.misses = 0

    def update(self, box: Optional[BBox]) -> Optional[BBox]:
        if box is not None:
            self.misses = 0

            if self.last_box is None:
                self.last_box = box
                return box

            x = int(self.alpha * box[0] + (1 - self.alpha) * self.last_box[0])
            y = int(self.alpha * box[1] + (1 - self.alpha) * self.last_box[1])
            w = int(self.alpha * box[2] + (1 - self.alpha) * self.last_box[2])
            h = int(self.alpha * box[3] + (1 - self.alpha) * self.last_box[3])

            self.last_box = (x, y, w, h)
            return self.last_box

        self.misses += 1
        if self.misses > self.max_misses:
            self.last_box = None
            return None

        return self.last_box


def normalize_kernel(k: int) -> int:
    if k < 3:
        k = BLUR_KERNEL
    if k % 2 == 0:
        k += 1
    return k


def detect_plate_box(frame: np.ndarray) -> Optional[BBox]:
    """
    Heuristic yellow-plate detector.
    Returns (x, y, w, h) or None.
    """
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


def expand_box(box: BBox, frame_shape: Tuple[int, int, int], ratio: float = 0.40) -> BBox:
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
    Blur the whole frame, then restore only the plate ROI from the original frame.
    Result: plate stays sharp, everything else is blurred.
    """
    blurred = cv2.GaussianBlur(frame, (kernel, kernel), 0)

    if plate_box is None:
        return blurred

    x, y, w, h = expand_box(plate_box, frame.shape, ratio=0.40)

    if w <= 0 or h <= 0:
        return blurred

    blurred[y:y + h, x:x + w] = frame[y:y + h, x:x + w]
    return blurred


def get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        raise RuntimeError("ffmpeg not found")


def process_ffmpeg(input_path: str, blur: int) -> bytes:
    """
    Full-frame fallback blur for cases where OpenCV cannot decode.
    This fallback does NOT preserve the plate.
    It is only for codec failure fallback.
    """
    ffmpeg = get_ffmpeg()
    out_path = tempfile.mktemp(suffix=".mp4")

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                input_path,
                "-vf",
                f"boxblur={blur}",
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
        )

        return Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)


def process_video(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
):
    """
    Main processor used by the review pipeline.

    Returns:
        processed_video_bytes, preview_jpeg_bytes
    """
    kernel = normalize_kernel(blur_strength or BLUR_KERNEL)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    cap = cv2.VideoCapture(input_path)

    if not cap.isOpened():
        processed = process_ffmpeg(input_path, kernel)
        Path(input_path).unlink(missing_ok=True)
        return processed, b""

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)

    if width <= 0 or height <= 0:
        cap.release()
        Path(input_path).unlink(missing_ok=True)
        processed = process_ffmpeg(input_path, kernel)
        return processed, b""

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
        processed = process_ffmpeg(input_path, kernel)
        return processed, b""

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
    """
    Compatibility wrapper for existing code paths in the repo.
    """
    processed_video_bytes, ticket_frame_jpeg = process_video(
        video_bytes=video_bytes,
        blur_strength=int(blur_kernel_size or BLUR_KERNEL),
        extract_frame_at=extract_frame_at,
    )

    # Placeholder plate result to preserve existing return signature.
    # If your repo expects OCR here, wire your OCR stage separately.
    best_plate = "1111111"

    return processed_video_bytes, ticket_frame_jpeg, best_plate
