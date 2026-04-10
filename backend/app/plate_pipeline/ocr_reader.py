"""OCR reader for plate crops with stronger preprocessing variants for Israeli plates."""

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


def _clean_digits(text: str) -> str:
    replacements = {
        "O": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "L": "1",
        "Z": "2",
        "S": "5",
        "B": "8",
    }
    text = text.upper().strip()
    text = "".join(replacements.get(ch, ch) for ch in text)
    return re.sub(r"\D", "", text)


def read_digits(img, psm: int = 7) -> str:
    if pytesseract is None:
        return ""
    try:
        text = pytesseract.image_to_string(
            img,
            config=f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789",
        )
        return _clean_digits(text)
    except Exception:
        return ""


def read_plate_crop(crop, psm_primary: int = 7, psm_fallbacks: tuple[int, ...] = (8, 6, 13)) -> tuple[str, Optional[str]]:
    best = ""
    for variant in _ocr_variants(crop):
        digits = read_digits(variant, psm_primary)
        if 7 <= len(digits) <= 8:
            return digits, None
        if len(digits) > len(best):
            best = digits
        for psm in psm_fallbacks:
            digits = read_digits(variant, psm)
            if 7 <= len(digits) <= 8:
                return digits, None
            if len(digits) > len(best):
                best = digits
    return best, (None if best else "OCR returned no digits")


def _ocr_variants(img) -> list[np.ndarray]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if getattr(img, "ndim", 2) == 3 else img
    gray = gray.astype(np.uint8)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 50, 50)
    gray = cv2.equalizeHist(gray)

    variants: list[np.ndarray] = [gray]
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)
    variants.append(255 - otsu)
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    variants.append(adaptive)
    variants.append(255 - adaptive)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.int16)
    variants.append(cv2.filter2D(gray, -1, kernel))
    return variants
