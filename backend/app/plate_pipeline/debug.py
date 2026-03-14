"""
Debug output: plate mask, crop, preprocessed crop, overlays.
Kept separate from business logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


def save_debug_frame(
    out_dir: Path,
    frame_idx: int,
    *,
    plate_mask: np.ndarray | None = None,
    plate_crop: np.ndarray | None = None,
    preprocessed_crop: np.ndarray | None = None,
    overlay: np.ndarray | None = None,
    curb_overlay: np.ndarray | None = None,
) -> None:
    """Save debug artifacts for a frame."""
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"frame_{frame_idx:05d}"
    if plate_mask is not None:
        cv2.imwrite(str(out_dir / f"{prefix}_mask.png"), plate_mask)
    if plate_crop is not None:
        cv2.imwrite(str(out_dir / f"{prefix}_crop.jpg"), plate_crop)
    if preprocessed_crop is not None:
        cv2.imwrite(str(out_dir / f"{prefix}_preprocessed.jpg"), preprocessed_crop)
    if overlay is not None:
        cv2.imwrite(str(out_dir / f"{prefix}_overlay.jpg"), overlay)
    if curb_overlay is not None:
        cv2.imwrite(str(out_dir / f"{prefix}_curb_overlay.jpg"), curb_overlay)


def draw_plate_box(frame: np.ndarray, bbox: tuple[int, int, int, int], color: tuple = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """Draw plate bbox on frame. Returns copy with overlay."""
    out = frame.copy()
    x, y, w, h = bbox
    cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness)
    return out
