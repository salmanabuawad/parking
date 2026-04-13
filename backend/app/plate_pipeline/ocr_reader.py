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

    # Mild denoise
    gray_dn = cv2.bilateralFilter(gray, 9, 50, 50)

    # CLAHE equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    gray_eq = clahe.apply(gray_dn)

    # Otsu threshold on equalized image
    _, otsu = cv2.threshold(gray_eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3 variants — fast, covers yellow plates well
    return [gray_eq, otsu, 255 - otsu]


def _ocr_variants_fast(img: np.ndarray) -> list[np.ndarray]:
    """Three preprocess variants for in-loop Tesseract (CPU-friendly).

    Variant order matters: HSV-Value channel is tried first because it gives
    best contrast for black digits on a yellow background.
    """
    h, w = img.shape[:2] if img.ndim == 3 else (img.shape[0], img.shape[1])
    scale = max(4.0, 320.0 / max(w, 1))

    # Variant 1: HSV Value channel — yellow background → bright, black digits → dark
    if img.ndim == 3:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        val = hsv[:, :, 2]
    else:
        val = img.copy()
    val = cv2.resize(val.astype(np.uint8), None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, val_thresh = cv2.threshold(val, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Variant 2: CLAHE-equalized grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    gray = cv2.resize(gray.astype(np.uint8), None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray_dn = cv2.bilateralFilter(gray, 9, 50, 50)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    gray_eq = clahe.apply(gray_dn)

    # Variant 3: Otsu on equalized
    _, otsu = cv2.threshold(gray_eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return [val_thresh, gray_eq, otsu]


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
    psm_fallbacks: tuple[int, ...] = (8,),
    use_easyocr: bool = False,
    fast: bool = False,
) -> tuple[str, Optional[str]]:
    """
    Input: raw BGR or grayscale crop from the ORIGINAL (unblurred) frame.

    * fast=True: 2 variants × PSM 7 only (frame loop, every N frames).
    * fast=False: 3 variants × primary + fallback PSMs (higher quality).
    * use_easyocr=True: run EasyOCR once on the raw crop (best-crop fallback only).
    """
    best = ""
    variants = _ocr_variants_fast(crop) if fast else _ocr_variants(crop)
    fallbacks = () if fast else psm_fallbacks

    for variant in variants:
        digits = read_digits_tesseract(variant, psm_primary)
        if 7 <= len(digits) <= 8:
            return digits, None
        if len(digits) > len(best):
            best = digits

        for psm in fallbacks:
            digits = read_digits_tesseract(variant, psm)
            if 7 <= len(digits) <= 8:
                return digits, None
            if len(digits) > len(best):
                best = digits

    if use_easyocr:
        digits = read_digits_easyocr(crop)
        if 7 <= len(digits) <= 8:
            return digits, None
        if len(digits) > len(best):
            best = digits

    return best, (None if best else "OCR returned no digits")
