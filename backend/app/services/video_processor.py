from __future__ import annotations

import cv2
import numpy as np
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

BLUR_KERNEL = 35
TRACK_MISSES = 8
SMOOTH_ALPHA = 0.65

HSV_LOWER_YELLOW = (10, 40, 40)
HSV_UPPER_YELLOW = (50, 255, 255)

BBox = Tuple[int, int, int, int]


# ---------------------------------------
# Tracker
# ---------------------------------------

@dataclass
class PlateTracker:
    max_misses: int = TRACK_MISSES
    alpha: float = SMOOTH_ALPHA

    def __post_init__(self):
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


# ---------------------------------------
# Plate Detection
# ---------------------------------------

def detect_plate_box(frame: np.ndarray) -> Optional[BBox]:

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(
        hsv,
        np.array(HSV_LOWER_YELLOW),
        np.array(HSV_UPPER_YELLOW),
    )

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0

    for c in contours:

        x, y, w, h = cv2.boundingRect(c)

        if w < 40 or h < 12:
            continue

        ratio = w / float(h)

        if ratio < 2 or ratio > 7:
            continue

        area = w * h

        if area > best_area:
            best_area = area
            best = (x, y, w, h)

    return best


# ---------------------------------------
# Blur logic
# ---------------------------------------

def normalize_kernel(k: int) -> int:

    if k < 3:
        k = BLUR_KERNEL

    if k % 2 == 0:
        k += 1

    return k


def expand_box(box: BBox, frame_shape, ratio=0.40):

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
):

    blurred = cv2.GaussianBlur(frame, (kernel, kernel), 0)

    if plate_box is None:
        return blurred

    x, y, w, h = expand_box(plate_box, frame.shape)

    if w <= 0 or h <= 0:
        return blurred

    # restore plate from original frame
    blurred[y:y + h, x:x + w] = frame[y:y + h, x:x + w]

    return blurred


# ---------------------------------------
# FFmpeg fallback
# ---------------------------------------

def get_ffmpeg():

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        ff = shutil.which("ffmpeg")
        if ff:
            return ff
        raise RuntimeError("ffmpeg not found")


def process_ffmpeg(input_path, blur):

    ffmpeg = get_ffmpeg()

    out = tempfile.mktemp(suffix=".mp4")

    subprocess.run([
        ffmpeg,
        "-y",
        "-i", input_path,
        "-vf", f"boxblur={blur}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out
    ], check=True)

    data = Path(out).read_bytes()

    Path(out).unlink(missing_ok=True)

    return data


# ---------------------------------------
# Main video processor
# ---------------------------------------

def process_video(
    video_bytes: bytes,
    blur_strength: int = 0,
    extract_frame_at: float = 0.5,
):

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        input_path = f.name

    cap = cv2.VideoCapture(input_path)

    if not cap.isOpened():
        return process_ffmpeg(input_path, blur_strength), b""

    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    raw = tempfile.mktemp(suffix=".mp4")

    writer = cv2.VideoWriter(
        raw,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height)
    )

    tracker = PlateTracker()

    kernel = normalize_kernel(blur_strength)

    frame_index = 0

    preview_frame = None
    preview_index = int(total * extract_frame_at)

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        plate = detect_plate_box(frame)

        plate = tracker.update(plate)

        out = blur_everything_except_plate(frame, plate, kernel)

        writer.write(out)

        if frame_index == preview_index:
            preview_frame = out.copy()

        frame_index += 1

    cap.release()
    writer.release()

    if frame_index == 0:
        return process_ffmpeg(input_path, blur_strength), b""

    # encode to H264
    ffmpeg = get_ffmpeg()

    out2 = tempfile.mktemp(suffix=".mp4")

    subprocess.run([
        ffmpeg,
        "-y",
        "-i", raw,
        "-c:v", "lib
