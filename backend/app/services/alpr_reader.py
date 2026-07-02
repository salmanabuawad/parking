"""Purpose-built ANPR reader — fast-alpr (YOLO-v9 license-plate detector + plate-trained OCR,
ONNX/CPU). Lazy singleton; degrades to [] if unavailable so the pipeline can fall back to the
HSV + Tesseract/EasyOCR path.

read_plates(frame) -> list of {"bbox": (x1,y1,x2,y2), "digits": str, "conf": float}
"""
from __future__ import annotations

import re

_ALPR = None
_FAILED = False


def _get_alpr():
    global _ALPR, _FAILED
    if _FAILED:
        return None
    if _ALPR is None:
        try:
            from fast_alpr import ALPR
            _ALPR = ALPR(
                detector_model="yolo-v9-t-384-license-plate-end2end",
                ocr_model="global-plates-mobile-vit-v2-model",
            )
            print("[alpr] fast-alpr loaded (YOLO-v9 plate detector + plate OCR)", flush=True)
        except Exception as e:  # missing package/model → fall back to legacy OCR
            print(f"[alpr] unavailable, using legacy OCR: {e}", flush=True)
            _FAILED = True
            return None
    return _ALPR


def read_plates(frame) -> list[dict]:
    alpr = _get_alpr()
    if alpr is None or frame is None:
        return []
    out: list[dict] = []
    try:
        for r in alpr.predict(frame):
            ocr = getattr(r, "ocr", None)
            digits = re.sub(r"\D", "", (getattr(ocr, "text", "") or "")) if ocr else ""
            if not digits:
                continue
            bb = r.detection.bounding_box
            out.append({
                "bbox": (int(bb.x1), int(bb.y1), int(bb.x2), int(bb.y2)),
                "digits": digits,
                "conf": float(getattr(r.detection, "confidence", 0.0) or 0.0),
            })
    except Exception as e:
        print(f"[alpr] predict failed: {e}", flush=True)
    return out
