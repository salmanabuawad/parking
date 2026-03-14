"""
Plate format classification from bounding-box ratio.
Israeli presets: private_long, private_rect, motorcycle, scooter.
"""
from __future__ import annotations

from typing import Any, Optional

from .config import PLATE_FORMAT_PRESETS


def classify_plate_format(box_w: int, box_h: int) -> Optional[dict[str, Any]]:
    """Return preset dict with name, width_cm, height_cm for selected format."""
    if box_h <= 0:
        return None
    ratio = box_w / box_h
    preset = min(PLATE_FORMAT_PRESETS, key=lambda p: abs(p["ratio"] - ratio))
    return dict(preset)
