"""Simple HSV plate engine — ported from the proven working script.

Algorithm (exact match to user's reference code):
  - Find largest yellow contour with aspect 2–6.5
  - Crop with 15px padding
  - Track sharpest crop across frames
  - OCR every 5 frames: gray → 6x resize → Tesseract PSM 7, digits only
  - Vote with Counter; normalise winner
  - Render: light blur (9,9), restore plate region, preview in corner, plate text at bottom
"""
from __future__ import annotations

import re
from collections import Counter, deque

import cv2
import numpy as np

try:
    import pytesseract
    from pathlib import Path
    for _p in [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]:
        if _p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(_p)
            break
except ImportError:
    pytesseract = None


def _clean(t: str) -> str:
    repl = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"}
    t = t.upper()
    t = "".join(repl.get(c, c) for c in t)
    return re.sub(r"[^0-9]", "", t)


def _valid(t: str) -> bool:
    return len(t) in (7, 8)


def _norm(t: str) -> str:
    if len(t) == 7:
        return f"{t[:2]}-{t[2:5]}-{t[5:]}"
    return f"{t[:3]}-{t[3:5]}-{t[5:]}"


def _detect_plate(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    """Find the largest yellow contour with aspect ratio 2–6.5. Returns xyxy or None."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([10, 70, 70]), np.array([45, 255, 255]))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    max_area = 0
    for c in cnts:
        x, y, wc, hc = cv2.boundingRect(c)
        if wc * hc < 80:
            continue
        ar = wc / (hc + 1e-5)
        if not (2.0 < ar < 6.5):
            continue
        if wc * hc > max_area:
            max_area = wc * hc
            best = (x, y, x + wc, y + hc)
    return best


def _run_ocr(crop: np.ndarray) -> str:
    """gray → 6x resize → Tesseract PSM 7 digits only."""
    if pytesseract is None:
        return ""
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
        txt = pytesseract.image_to_string(
            gray,
            config="--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789",
        )
        return _clean(txt)
    except Exception:
        return ""


class EnterprisePlateEngine:
    """Stateful per-video processor. Call process_frame() for each frame."""

    def __init__(self, blur_kernel: int = 9, ocr_every: int = 5, **_ignored):
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        self.ocr_every = max(1, ocr_every)

        self.reads: list[str] = []
        self.best_crop: np.ndarray | None = None
        self.best_sharp: float = 0.0
        self.last_crop: np.ndarray | None = None
        self.frame_i: int = 0

        # Expose for pipeline result extraction
        self.tracks: dict = {}          # kept for pipeline compat (single pseudo-track)
        self.next_track_id: int = 1

    # ── per-frame ──────────────────────────────────────────────────────────

    def detect_plate_candidates(self, frame: np.ndarray) -> list[dict]:
        """Return list with 0 or 1 detection dict (xyxy bbox)."""
        bbox = _detect_plate(frame)
        if bbox is None:
            return []
        x1, y1, x2, y2 = bbox
        return [{"bbox": bbox, "confidence": float((x2 - x1) * (y2 - y1))}]

    def update_tracks(self, detections: list[dict], frame_index: int) -> None:
        """Maintain a single pseudo-track for the best plate candidate."""
        if detections:
            d = detections[0]
            if 1 not in self.tracks:
                self.tracks[1] = {
                    "track_id": 1,
                    "bbox": d["bbox"],
                    "detector_confidence": d["confidence"],
                    "ocr_history": deque(maxlen=20),
                    "best_crop": None,
                    "best_sharpness": -1.0,
                    "last_seen": frame_index,
                    "best_digits": None,
                    "best_plate": None,
                    "vote_count": 0,
                }
            else:
                self.tracks[1]["bbox"] = d["bbox"]
                self.tracks[1]["last_seen"] = frame_index
        else:
            # Expire track after 15 missed frames
            if 1 in self.tracks and frame_index - self.tracks[1]["last_seen"] > 15:
                del self.tracks[1]

    def extract_crop(self, frame: np.ndarray, bbox, pad: int = 15) -> np.ndarray | None:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]
        return crop.copy() if crop.size else None

    def update_track_crop(self, track: dict, crop: np.ndarray) -> None:
        if crop is None or crop.size == 0:
            return
        sharp = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        if sharp > track["best_sharpness"]:
            track["best_sharpness"] = sharp
            track["best_crop"] = crop.copy()
        # Also keep global bests for OCR
        if sharp > self.best_sharp:
            self.best_sharp = sharp
            self.best_crop = crop.copy()
        self.last_crop = crop.copy()

    def update_track_text(self, track: dict, raw_reads: list[str]) -> None:
        for digits in raw_reads:
            d = _clean(digits)
            if _valid(d):
                track["ocr_history"].append(d)
                self.reads.append(d)
        if track["ocr_history"]:
            best_d, vc = Counter(track["ocr_history"]).most_common(1)[0]
            track["best_digits"] = best_d
            track["best_plate"] = _norm(best_d)
            track["vote_count"] = vc

    def select_best_track(self) -> dict | None:
        if not self.tracks:
            return None
        return max(self.tracks.values(), key=lambda t: (t.get("vote_count", 0), t.get("detector_confidence", 0)))

    def best_result(self) -> str | None:
        """Return normalised plate number from votes, or None."""
        if not self.reads:
            return None
        digits = Counter(self.reads).most_common(1)[0][0]
        return _norm(digits)

    # ── rendering (exact match to reference script) ─────────────────────

    def render_frame(self, original_frame: np.ndarray) -> np.ndarray:
        fh, fw = original_frame.shape[:2]
        best_bbox = self.tracks.get(1, {}).get("bbox") if self.tracks else None
        crop = self.last_crop

        # Light blur on whole frame
        k = max(3, self.blur_kernel | 1)
        out = cv2.GaussianBlur(original_frame, (k, k), 0)

        # Restore plate region sharp
        if best_bbox:
            x1, y1, x2, y2 = best_bbox
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(fw, x2); y2 = min(fh, y2)
            out[y1:y2, x1:x2] = original_frame[y1:y2, x1:x2]

        # Preview crop in top-left corner
        if crop is not None and crop.size > 0:
            p = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            ph = min(p.shape[0], int(fh * 0.20))
            pw = min(p.shape[1], int(fw * 0.28))
            p = cv2.resize(p, (pw, ph), interpolation=cv2.INTER_CUBIC)
            out[10:10 + ph, 10:10 + pw] = p

        # Plate text at bottom
        best_txt = self.best_result()
        if best_txt:
            cv2.putText(out, best_txt, (10, fh - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(out, best_txt, (10, fh - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

        return out
