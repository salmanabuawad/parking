"""License plate OCR (pytesseract-based, matches ref interface)."""
from __future__ import annotations

import re
from pathlib import Path

import pytesseract

# Set Tesseract path on Windows if not in PATH
for _p in [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]:
    if _p.exists():
        pytesseract.pytesseract.tesseract_cmd = str(_p)
        break

from app.violation.schemas import Detection, PlateRead
from app.violation.utils.image import crop_bbox
from app.violation.utils.text import normalize_plate_text


class PlateOCRService:
    def read_plate_from_vehicle(self, frame, vehicle: Detection) -> PlateRead | None:
        roi = crop_bbox(frame, vehicle.bbox)
        if roi.size == 0:
            return None
        try:
            text = pytesseract.image_to_string(roi, config="--psm 7")
            cleaned = re.sub(r"[^A-Za-z0-9]", "", text.strip())
            if len(cleaned) < 4 or len(cleaned) > 12:
                return None
            vx1, vy1, _, _ = vehicle.bbox
            return PlateRead(
                text=normalize_plate_text(cleaned).upper() or cleaned.upper(),
                confidence=0.8,
                bbox=vehicle.bbox,
            )
        except Exception:
            return None
