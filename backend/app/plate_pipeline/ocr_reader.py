"""OCR reader for plate crops — Israeli plates (7–8 digits).

Key design:
- Accepts raw BGR OR grayscale crop from the ORIGINAL (unblurred) frame
- Generates 6 preprocessing variants internally (no external pre-processing needed)
- Tries Tesseract (all PSMs) then EasyOCR
- Applies letter→digit replacements BEFORE length validation
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# ── Tesseract ──────────────────────────────────────────────────────────────
try:
    import pytesseract

    for _p in [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]:
        if _p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(_p)
            break
except ImportError:
    pytesseract = None

# ── EasyOCR (lazy, singleton) ──────────────────────────────────────────────
_easyocr_reader = None
_easyocr_failed = False


def _get_easyocr():
    global _easyocr_reader, _easyocr_failed
    if _easyocr_failed:
        return None
    if _easyocr_reader is None:
        try:
            import easyocr  # noqa: PLC0415
            _easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        except Exception:
            _easyocr_failed = True
    return _easyocr_reader


# ── Text cleanup ───────────────────────────────────────────────────────────

def clean_plate_text(text: str) -> str:
    """Map letter look-alikes → digits, then keep digits only."""
    _REPLACEMENTS = {
        "O": "0", "Q": "0", "D": "0",
        "I": "1", "L": "1",
        "Z": "2",
        "S": "5",
        "B": "8",
    }
    text = text.upper().strip()
    text = "".join(_REPLACEMENTS.get(ch, ch) for ch in text)
    return re.sub(r"\D", "", text)


# ── Variant generation ─────────────────────────────────────────────────────

def _ocr_variants(img: np.ndarray) -> list[np.ndarray]:
    """
    Generate 6 preprocessing variants from a BGR or grayscale plate crop.

    Upscales to ≥400 px wide so Tesseract can read small plates.
    Returns a list of uint8 grayscale images.
    """
    # Convert to grayscale
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    gray = gray.astype(np.uint8)

    # Upscale: ensure at least 6× OR 400 px wide, whichever is bigger
    h, w = gray.shape[:2]
    scale = max(6.0, 400.0 / max(w, 1))
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Mild denoise (preserves edges better than NlMeans for small upscaled crops)
    gray_dn = cv2.bilateralFilter(gray, 9, 50, 50)

    # CLAHE equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    gray_eq = clahe.apply(gray_dn)

    # Otsu threshold on equalized image
    _, otsu = cv2.threshold(gray_eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Adaptive threshold on denoised image
    adaptive = cv2.adaptiveThreshold(
        gray_dn, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4
    )

    return [
        gray_eq,        # equalized — best for yellow plates with CLAHE
        otsu,           # Otsu binary — clean dark-on-bright
        255 - otsu,     # inverted Otsu — bright-on-dark
        adaptive,       # local adaptive — handles uneven lighting
        255 - adaptive, # inverted adaptive
        gray,           # raw rescaled gray — baseline
    ]


# ── Tesseract OCR ──────────────────────────────────────────────────────────

def read_digits_tesseract(img: np.ndarray, psm: int = 7) -> str:
    """Run Tesseract digit extraction. Whitelist = 0-9 only."""
    if pytesseract is None:
        return ""
    try:
        text = pytesseract.image_to_string(
            img,
            config=f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789",
        )
        return clean_plate_text(text)
    except Exception:
        return ""


# ── EasyOCR fallback ───────────────────────────────────────────────────────

def read_digits_easyocr(img: np.ndarray) -> str:
    """Run EasyOCR, apply letter→digit replacement."""
    reader = _get_easyocr()
    if reader is None:
        return ""
    try:
        # EasyOCR works on BGR or gray
        results = reader.readtext(img, detail=0)
        text = " ".join(str(r) for r in results)
        return clean_plate_text(text)
    except Exception:
        return ""


# ── Main entry ─────────────────────────────────────────────────────────────

def read_plate_crop(
    crop: np.ndarray,
    psm_primary: int = 7,
    psm_fallbacks: tuple[int, ...] = (8, 6, 13),
) -> tuple[str, Optional[str]]:
    """
    Try all OCR variants + PSM modes, then EasyOCR.
    Input: raw BGR or grayscale crop from the ORIGINAL frame.
    Returns: (best_digits_str, error_reason_or_None)
    """
    best = ""

    for variant in _ocr_variants(crop):
        # Primary PSM
        digits = read_digits_tesseract(variant, psm_primary)
        if 7 <= len(digits) <= 8:
            return digits, None
        if len(digits) > len(best):
            best = digits

        # Fallback PSMs
        for psm in psm_fallbacks:
            digits = read_digits_tesseract(variant, psm)
            if 7 <= len(digits) <= 8:
                return digits, None
            if len(digits) > len(best):
                best = digits

    # EasyOCR as last resort (on the raw crop, not a variant)
    digits = read_digits_easyocr(crop)
    if 7 <= len(digits) <= 8:
        return digits, None
    if len(digits) > len(best):
        best = digits

    return best, (None if best else "OCR returned no digits")
