"""
OCR reader for plate crops.
Failure-safe: returns empty string on any error.
Uses Tesseract with configurable PSM; tries fallback PSMs.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    import pytesseract
    from pathlib import Path
    for p in [Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"), Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")]:
        if p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(p)
            break
except ImportError:
    pytesseract = None


def read_digits(img, psm: int = 7) -> str:
    """Run Tesseract with digit whitelist. Returns normalized digits only."""
    if pytesseract is None:
        return ""
    try:
        text = pytesseract.image_to_string(
            img,
            config=f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789",
        )
        return re.sub(r"\D", "", text.strip())
    except Exception:
        return ""


def read_plate_crop(
    crop,
    psm_primary: int = 7,
    psm_fallbacks: tuple[int, ...] = (6, 8),
) -> tuple[str, Optional[str]]:
    """
    OCR a preprocessed plate crop.
    Returns (digits, error_message).
    error_message is None on success.
    """
    digits = read_digits(crop, psm_primary)
    if digits:
        return digits, None
    for psm in psm_fallbacks:
        digits = read_digits(crop, psm)
        if digits:
            return digits, None
    return "", "OCR returned no digits"
