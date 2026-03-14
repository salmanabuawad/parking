"""OCR reader for plate crops with light preprocessing variants."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    import pytesseract

    for p in [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]:
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
    """OCR a preprocessed plate crop. Returns (digits, error_message)."""
    for variant in _ocr_variants(crop):
        digits = read_digits(variant, psm_primary)
        if digits:
            return digits, None
        for psm in psm_fallbacks:
            digits = read_digits(variant, psm)
            if digits:
                return digits, None
    return "", "OCR returned no digits"


def _ocr_variants(img) -> list[np.ndarray]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if getattr(img, "ndim", 2) == 3 else img
    gray = gray.astype(np.uint8)

    variants: list[np.ndarray] = [gray]

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    variants.append(clahe)

    _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)

    adaptive = cv2.adaptiveThreshold(
        clahe,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    variants.append(adaptive)

    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.int16)
    sharp = cv2.filter2D(clahe, -1, kernel)
    variants.append(sharp)

    return variants
