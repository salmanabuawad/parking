"""Grab a calibration frame for a camera — from RTSP, an uploaded video, or an uploaded image —
encode it as JPEG, and report its pixel resolution. Enforcement-section polygons are stored in
these pixels (the camera's calibration_width/height), so the frontend can scale to any display.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np


def _encode_jpeg(frame) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return buf.tobytes() if ok else b""


def grab_rtsp_frame(rtsp_url: str) -> tuple[bytes, int, int] | None:
    """Open the RTSP stream and read one frame. Returns (jpeg, width, height) or None."""
    cap = cv2.VideoCapture(rtsp_url)
    try:
        # A couple of reads — the first grab off an RTSP stream is often empty.
        frame = None
        for _ in range(5):
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
                break
        if frame is None:
            return None
        h, w = frame.shape[:2]
        return _encode_jpeg(frame), w, h
    finally:
        cap.release()


def frame_from_video_bytes(video_bytes: bytes) -> tuple[bytes, int, int] | None:
    """Extract one calibration frame (~1s in) from an uploaded video clip."""
    tmp = Path(tempfile.mktemp(suffix=".mp4"))
    tmp.write_bytes(video_bytes)
    try:
        cap = cv2.VideoCapture(str(tmp))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps))  # ~1 second in
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return None
        h, w = frame.shape[:2]
        return _encode_jpeg(frame), w, h
    finally:
        tmp.unlink(missing_ok=True)


def normalize_image_bytes(img_bytes: bytes) -> tuple[bytes, int, int] | None:
    """Decode an uploaded image, return (jpeg, width, height)."""
    arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return None
    h, w = frame.shape[:2]
    return _encode_jpeg(frame), w, h
