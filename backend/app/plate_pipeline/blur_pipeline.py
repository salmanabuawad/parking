"""
Privacy rendering pipeline.
- Light blur on whole frame (kernel from config; smaller = less blur)
- Restore best plate bbox sharply in-scene only (no corner inset — avoids duplicating the plate as a second "frame")
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import BLUR_KERNEL_SIZE

BBox = tuple[int, int, int, int]


def _normalize_kernel(k: int) -> int:
    if k < 3:
        k = BLUR_KERNEL_SIZE
    if k % 2 == 0:
        k += 1
    return k


def blur_frame(frame: np.ndarray, kernel_size: int = BLUR_KERNEL_SIZE) -> np.ndarray:
    k = _normalize_kernel(kernel_size)
    return cv2.GaussianBlur(frame, (k, k), 0)


def restore_plate_region(blurred: np.ndarray, sharp_crop: np.ndarray, bbox: BBox) -> np.ndarray:
    x, y, w, h = bbox
    h_f, w_f = blurred.shape[:2]
    if w <= 0 or h <= 0 or sharp_crop.size == 0:
        return blurred
    if sharp_crop.shape[1] != w or sharp_crop.shape[0] != h:
        sharp_crop = cv2.resize(sharp_crop, (w, h), interpolation=cv2.INTER_CUBIC)
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w_f, x + w), min(h_f, y + h)
    cx1 = x1 - x
    cy1 = y1 - y
    cx2 = cx1 + (x2 - x1)
    cy2 = cy1 + (y2 - y1)
    if cx2 <= cx1 or cy2 <= cy1:
        return blurred
    out = blurred.copy()
    out[y1:y2, x1:x2] = sharp_crop[cy1:cy2, cx1:cx2]
    return out


def blur_except_plate(frame: np.ndarray, plate_bbox: BBox | None, kernel_size: int = BLUR_KERNEL_SIZE) -> np.ndarray:
    blurred = blur_frame(frame, kernel_size)
    if plate_bbox is None:
        return blurred
    x, y, w, h = plate_bbox
    sharp = frame[y : y + h, x : x + w].copy()
    return restore_plate_region(blurred, sharp, plate_bbox)


def render_privacy_frame(
    frame: np.ndarray,
    plate_bboxes: list[BBox] | None,
    kernel_size: int = BLUR_KERNEL_SIZE,
    preview_crop: np.ndarray | None = None,
    plate_text: str | None = None,
    preview_max_w_ratio: float = 0.28,
    preview_max_h_ratio: float = 0.20,
    preview_margin_px: int = 10,
    preview_zoom: float = 4.0,
) -> np.ndarray:
    out = blur_frame(frame, kernel_size)
    plate_bboxes = plate_bboxes or []

    for x, y, w, h in plate_bboxes:
        if w <= 0 or h <= 0:
            continue
        crop = frame[max(0, y):max(0, y) + h, max(0, x):max(0, x) + w].copy()
        out = restore_plate_region(out, crop, (x, y, w, h))
        cv2.rectangle(out, (x, y), (x + w, y + h), (255, 255, 255), 1)

    if preview_crop is not None and preview_crop.size > 0:
        h_frame, w_frame = out.shape[:2]
        ph, pw = preview_crop.shape[:2]
        zoom = cv2.resize(
            preview_crop,
            (max(1, int(pw * preview_zoom)), max(1, int(ph * preview_zoom))),
            interpolation=cv2.INTER_CUBIC,
        )
        zh, zw = zoom.shape[:2]
        max_w = int(w_frame * preview_max_w_ratio)
        max_h = int(h_frame * preview_max_h_ratio)
        scale = min(max_w / max(zw, 1), max_h / max(zh, 1), 1.0)
        zoom = cv2.resize(zoom, (max(1, int(zw * scale)), max(1, int(zh * scale))), interpolation=cv2.INTER_CUBIC)
        zh, zw = zoom.shape[:2]
        x0 = preview_margin_px
        y0 = preview_margin_px
        out[y0:y0 + zh, x0:x0 + zw] = zoom
        cv2.putText(out, "PLATE VIEW", (x0, min(h_frame - 6, y0 + zh + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    if plate_text:
        cv2.putText(out, plate_text, (10, out.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    return out


def render_privacy_frame_tracks(
    frame: np.ndarray,
    plate_bboxes: list[BBox],
    kernel_size: int = BLUR_KERNEL_SIZE,
) -> np.ndarray:
    """
    Privacy frame: blur background, restore plate bbox(s) in-place.
    Plate number is drawn once in overlay_track_plate_labels (final pass), not here.
    """
    out = blur_frame(frame, kernel_size)
    plate_bboxes = plate_bboxes or []

    for x, y, w, h in plate_bboxes:
        if w <= 0 or h <= 0:
            continue
        y0, y1 = max(0, y), max(0, y) + h
        x0, x1 = max(0, x), max(0, x) + w
        crop = frame[y0:y1, x0:x1].copy()
        out = restore_plate_region(out, crop, (x, y, w, h))
        cv2.rectangle(out, (x, y), (x + w, y + h), (255, 255, 255), 1)

    return out


def overlay_track_plate_labels(
    frame_bgr: np.ndarray,
    labels_xywh: list[tuple[BBox, str]],
) -> np.ndarray:
    """Draw normalized plate strings near each bbox (on an already-rendered frame)."""
    out = frame_bgr
    h = out.shape[0]
    for (x, y, w, hbox), text in labels_xywh:
        if not text:
            continue
        ty = min(h - 8, y + hbox + 20)
        cv2.putText(
            out,
            text,
            (max(4, x), ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return out
