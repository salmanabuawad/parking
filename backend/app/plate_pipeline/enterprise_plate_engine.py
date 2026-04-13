"""HSV + IOU tracking + single best preview — enterprise plate video engine."""
from __future__ import annotations

import cv2
import numpy as np
from collections import Counter, deque


class EnterprisePlateEngine:
    def __init__(
        self,
        blur_kernel: int = 3,
        min_plate_area: int = 80,
        preview_scale: float = 4.0,
        keep_last_preview: bool = True,
        detection_zoom: float = 1.75,
        detection_roi_y_start: float = 0.26,
    ):
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        self.min_plate_area = min_plate_area
        self.preview_scale = preview_scale
        self.keep_last_preview = keep_last_preview
        self.detection_zoom = max(1.0, float(detection_zoom))
        self.detection_roi_y_start = min(0.85, max(0.0, float(detection_roi_y_start)))

        self.next_track_id = 1
        self.tracks: dict = {}
        self.last_best_preview = None

    @staticmethod
    def clean_plate_text(text: str) -> str:
        replacements = {
            "O": "0",
            "Q": "0",
            "D": "0",
            "I": "1",
            "L": "1",
            "S": "5",
            "B": "8",
            "Z": "2",
        }
        text = text.upper().strip()
        text = "".join(replacements.get(ch, ch) for ch in text)
        text = "".join(ch for ch in text if ch.isdigit())
        return text

    @staticmethod
    def is_valid_plate(digits: str) -> bool:
        return digits.isdigit() and len(digits) in (7, 8)

    @staticmethod
    def normalize_plate(digits: str):
        if len(digits) == 7:
            return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
        if len(digits) == 8:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return None

    @staticmethod
    def iou(a, b) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih

        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter

        return inter / union if union > 0 else 0.0

    @staticmethod
    def laplacian_var(img: np.ndarray) -> float:
        return float(cv2.Laplacian(img, cv2.CV_64F).var())

    def _detect_raw_on_image(self, frame: np.ndarray, min_area: int) -> list:
        """HSV + contour plate candidates; bbox xyxy in ``frame`` coordinates."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([15, 80, 100]), np.array([38, 255, 255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            if area < min_area:
                continue

            aspect = w / (h + 1e-5)
            if not (2.0 <= aspect <= 6.5):
                continue

            roi = frame[y : y + h, x : x + w]
            if roi.size == 0:
                continue

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 80, 200).mean()
            score = float(area + edges * 30)

            detections.append(
                {
                    "bbox": (x, y, x + w, y + h),
                    "confidence": score,
                }
            )

        return detections

    def _merge_detections(self, detections: list, iou_thresh: float = 0.45) -> list:
        """Greedy NMS: keep higher-confidence boxes first."""
        dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
        kept: list = []
        for d in dets:
            bb = d["bbox"]
            if any(self.iou(bb, k["bbox"]) >= iou_thresh for k in kept):
                continue
            kept.append(d)
        return kept

    def detect_plate_candidates(self, frame: np.ndarray):
        """Full-frame pass + zoomed lower ROI (plates occupy more pixels → better HSV/Canny)."""
        fh, fw = frame.shape[:2]
        all_dets: list = []

        # Full resolution, full frame
        all_dets.extend(self._detect_raw_on_image(frame, self.min_plate_area))

        z = self.detection_zoom
        y0 = int(fh * self.detection_roi_y_start)
        if z > 1.001 and y0 < fh - 32:
            roi = frame[y0:fh, 0:fw]
            rh, rw = roi.shape[:2]
            if rh >= 24 and rw >= 24:
                scaled = cv2.resize(
                    roi,
                    (int(rw * z), int(rh * z)),
                    interpolation=cv2.INTER_CUBIC,
                )
                min_az = max(self.min_plate_area, int(self.min_plate_area * z * z))
                for d in self._detect_raw_on_image(scaled, min_az):
                    x1, y1, x2, y2 = d["bbox"]
                    mx1 = int(round(x1 / z))
                    mx2 = int(round(x2 / z))
                    my1 = int(round(y1 / z)) + y0
                    my2 = int(round(y2 / z)) + y0
                    mx1 = max(0, min(mx1, fw - 1))
                    mx2 = max(0, min(mx2, fw))
                    my1 = max(0, min(my1, fh - 1))
                    my2 = max(0, min(my2, fh))
                    if mx2 <= mx1 or my2 <= my1:
                        continue
                    all_dets.append({"bbox": (mx1, my1, mx2, my2), "confidence": d["confidence"]})

        merged = self._merge_detections(all_dets, iou_thresh=0.45)
        merged.sort(key=lambda d: d["confidence"], reverse=True)
        return merged

    def update_tracks(self, detections, frame_index: int):
        assigned = set()

        for track_id, track in list(self.tracks.items()):
            best_det = None
            best_iou = 0.0

            for i, det in enumerate(detections):
                if i in assigned:
                    continue
                score = self.iou(track["bbox"], det["bbox"])
                if score > best_iou:
                    best_iou = score
                    best_det = (i, det)

            if best_det and best_iou >= 0.3:
                i, det = best_det
                assigned.add(i)
                track["bbox"] = det["bbox"]
                track["detector_confidence"] = det["confidence"]
                track["last_seen"] = frame_index
            elif frame_index - track["last_seen"] > 10:
                del self.tracks[track_id]

        for i, det in enumerate(detections):
            if i in assigned:
                continue
            self.tracks[self.next_track_id] = {
                "track_id": self.next_track_id,
                "bbox": det["bbox"],
                "detector_confidence": det["confidence"],
                "ocr_history": deque(maxlen=20),
                "best_crop": None,
                "best_sharpness": -1.0,
                "last_seen": frame_index,
                "best_digits": None,
                "best_plate": None,
                "vote_count": 0,
            }
            self.next_track_id += 1

    def extract_crop(self, frame: np.ndarray, bbox, pad: int = 14):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        return frame[y1:y2, x1:x2].copy()

    def update_track_crop(self, track, crop: np.ndarray):
        if crop is None or crop.size == 0:
            return
        sharpness = self.laplacian_var(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
        if sharpness > track["best_sharpness"]:
            track["best_sharpness"] = sharpness
            track["best_crop"] = crop.copy()

    def update_track_text(self, track, raw_reads):
        cleaned = [self.clean_plate_text(t) for t in raw_reads]
        valid = [t for t in cleaned if self.is_valid_plate(t)]

        for digits in valid:
            track["ocr_history"].append(digits)

        if track["ocr_history"]:
            counts = Counter(track["ocr_history"])
            best_digits, vote_count = counts.most_common(1)[0]
            track["best_digits"] = best_digits
            track["best_plate"] = self.normalize_plate(best_digits)
            track["vote_count"] = vote_count

    def select_best_track(self):
        active = list(self.tracks.values())
        if not active:
            return None

        active.sort(
            key=lambda t: (
                t.get("vote_count", 0),
                t.get("detector_confidence", 0.0),
                t.get("last_seen", 0),
            ),
            reverse=True,
        )
        return active[0]

    def render_frame(self, original_frame: np.ndarray):
        k = max(3, self.blur_kernel | 1)
        frame = cv2.GaussianBlur(original_frame, (k, k), 0)

        fh, fw = frame.shape[:2]
        pad = 8
        for track in self.tracks.values():
            x1, y1, x2, y2 = track["bbox"]
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(fw, x2 + pad)
            y2 = min(fh, y2 + pad)
            frame[y1:y2, x1:x2] = original_frame[y1:y2, x1:x2]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)

        # SINGLE BEST PREVIEW ONLY
        best = self.select_best_track()
        preview_crop = None

        if best and best.get("best_crop") is not None:
            preview_crop = best["best_crop"]
            self.last_best_preview = preview_crop.copy()
        elif self.keep_last_preview and self.last_best_preview is not None:
            preview_crop = self.last_best_preview

        if preview_crop is not None and preview_crop.size > 0:
            ph, pw = preview_crop.shape[:2]
            preview = cv2.resize(
                preview_crop,
                (int(pw * self.preview_scale), int(ph * self.preview_scale)),
                interpolation=cv2.INTER_CUBIC,
            )

            h, w = frame.shape[:2]
            max_w = int(w * 0.28)
            max_h = int(h * 0.20)

            scale = min(
                max_w / max(preview.shape[1], 1),
                max_h / max(preview.shape[0], 1),
                1.0,
            )

            preview = cv2.resize(
                preview,
                (
                    max(1, int(preview.shape[1] * scale)),
                    max(1, int(preview.shape[0] * scale)),
                ),
                interpolation=cv2.INTER_CUBIC,
            )

            ph2, pw2 = preview.shape[:2]
            frame[10 : 10 + ph2, 10 : 10 + pw2] = preview

        if best and best.get("best_plate"):
            # Keep the caption strip sharp (text was drawn on blurred pixels before).
            band_h = min(64, max(40, fh // 5))
            y0 = max(0, fh - band_h)
            frame[y0:fh, :] = original_frame[y0:fh, :].copy()
            txt = best["best_plate"]
            bx, by = 12, fh - 18
            cv2.putText(
                frame,
                txt,
                (bx, by),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 0),
                4,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                txt,
                (bx, by),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        return frame
