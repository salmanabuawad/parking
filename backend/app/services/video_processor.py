
from __future__ import annotations

import cv2
import numpy as np
import tempfile
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

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

    while True:

        ret, frame = cap.read()
        if not ret:
            break

        plate = detect_plate_box(frame)

        tracked = tracker.update(plate)

        output = blur_everything_except_plate(frame, tracked, kernel)

        writer.write(output)

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

    Path(temp_out).unlink(missing_ok=True)
    Path(final_path).unlink(missing_ok=True)
    Path(input_path).unlink(missing_ok=True)

    return video


def process_video_fast_hsv(video_bytes: bytes, blur_strength: int = DEFAULT_BLUR):
    return process_video(video_bytes, blur_strength)


def process_video_with_violation_pipeline(video_bytes: bytes, blur_kernel_size: int | None = None):

    processed = process_video(video_bytes, blur_kernel_size or DEFAULT_BLUR)

    return processed, b"", "UNKNOWN"
