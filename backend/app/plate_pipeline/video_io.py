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
    stride: int = 1,
) -> Iterator[tuple[int, "cv2.Mat"]]:
    """Yield (frame_idx, frame) from video. With stride>1, keep every `stride`-th source frame so
    the kept frames span the WHOLE clip (frame_idx is the sequential kept index 0,1,2,…), stopping
    after max_frames kept frames. grab()/retrieve() so skipped frames aren't fully decoded."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        print(f"[video_io] ERROR: cannot open video for frame decode: {path}", flush=True)
        return
    stride = max(1, int(stride or 1))
    src = 0
    kept = 0
    try:
        while True:
            if max_frames is not None and kept >= max_frames:
                break
            if not cap.grab():
                break
            if src % stride == 0:
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    break
                yield kept, frame
                kept += 1
            src += 1
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
