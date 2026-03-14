"""
Video I/O: read frames, write output.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2


def read_frames(
    path: Path,
    max_frames: int | None = None,
) -> Iterator[tuple[int, "cv2.Mat"]]:
    """Yield (frame_idx, frame) from video. Stops at max_frames if set."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return
    idx = 0
    try:
        while True:
            if max_frames is not None and idx >= max_frames:
                break
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            yield idx, frame
            idx += 1
    finally:
        cap.release()


def get_video_info(path: Path) -> dict | None:
    """Return fps, width, height, frame_count if readable."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS) or 25,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
    }
    cap.release()
    return info
