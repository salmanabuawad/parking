"""
OCR preprocessing pipeline.
Preprocess only the plate crop before OCR:
- grayscale, resize 2x/3x, contrast, optional denoise/threshold/sharpen.
Configurable via config.
"""
from __future__ import annotations

import cv2
import numpy as np


def preprocess_for_ocr(
    crop: np.ndarray,
    *,
    resize_factor: int = 2,
    denoise: bool = True,
    sharpen: bool = True,
    contrast: bool = True,
) -> np.ndarray:
    """
    Preprocess a tight plate crop for OCR.
    Returns grayscale image ready for Tesseract.
    """
    if crop.size == 0:
        return crop
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    if resize_factor > 1:
        h, w = gray.shape[:2]
        gray = cv2.resize(
            gray,
            (w * resize_factor, h * resize_factor),
            interpolation=cv2.INTER_CUBIC,
        )
    if denoise:
        gray = cv2.fastNlMeansDenoising(gray, None, h=6, templateWindowSize=7, searchWindowSize=21)
    if contrast:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        gray = clahe.apply(gray)
    if sharpen:
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        gray = cv2.filter2D(gray, -1, kernel)
    return gray


def preprocess_black_on_yellow(crop: np.ndarray) -> np.ndarray:
    """Black-on-yellow enhancement: adaptive threshold, invert for Tesseract preference."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    return cv2.bitwise_not(binary)
