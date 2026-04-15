"""
Multi-plate ANPR: IOU-based tracking, per-track OCR voting, Israeli private format normalization.
All coordinates: detections use xyxy; internal smoothing uses xyxy; crop APIs use xywh.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

BBoxXYXY = tuple[int, int, int, int]
BBoxXYWH = tuple[int, int, int, int]


def xywh_to_xyxy(b: BBoxXYWH) -> BBoxXYXY:
    x, y, w, h = b
    return (x, y, x + w, y + h)


def xyxy_to_xywh(b: BBoxXYXY) -> BBoxXYWH:
    x1, y1, x2, y2 = b
    return (x1, y1, max(0, x2 - x1), max(0, y2 - y1))


def iou_xyxy(a: BBoxXYXY, b: BBoxXYXY) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def smooth_xyxy(
    prev: BBoxXYXY,
    det: BBoxXYXY,
    alpha: float,
) -> BBoxXYXY:
    return tuple(int(alpha * d + (1 - alpha) * p) for p, d in zip(prev, det))  # type: ignore[return-value]


def is_valid_israeli_private_digits(digits: str) -> bool:
    d = re.sub(r"\D", "", digits)
    return len(d) in (7, 8)


def normalize_israeli_private_plate(digits: str) -> Optional[str]:
    """7 digits → dd-ddd-dd; 8 digits → ddd-dd-ddd."""
    d = re.sub(r"\D", "", digits)
    if len(d) == 7:
        return f"{d[0:2]}-{d[2:5]}-{d[5:7]}"
    if len(d) == 8:
        return f"{d[0:3]}-{d[3:5]}-{d[5:8]}"
    return None


def raw_digits_only(digits: str) -> str:
    return re.sub(r"\D", "", digits)


@dataclass
class PlateDetectionXYXY:
    """Single frame detection output."""

    bbox: BBoxXYXY  # x1, y1, x2, y2
    confidence: float

    def to_dict(self) -> dict:
        return {"bbox": [self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3]], "confidence": float(self.confidence)}


@dataclass
class PlateTrackState:
    track_id: int
    bbox_xyxy: BBoxXYXY
    ocr_counter: Counter[str] = field(default_factory=Counter)
    ocr_history: list[str] = field(default_factory=list)
    best_crop: Optional[np.ndarray] = None
    best_sharpness: float = -1.0
    last_seen_frame: int = 0
    miss_count: int = 0

    @property
    def bbox_xywh(self) -> BBoxXYWH:
        return xyxy_to_xywh(self.bbox_xyxy)

    def add_ocr_sample(self, raw_digits: str) -> None:
        self.ocr_history.append(raw_digits)
        d = raw_digits_only(raw_digits)
        if len(d) in (7, 8):
            self.ocr_counter[d] += 1

    def best_vote(self) -> tuple[Optional[str], int]:
        """Return (raw_7_or_8_digits, vote_count) for winner."""
        if not self.ocr_counter:
            return None, 0
        plate, count = self.ocr_counter.most_common(1)[0]
        return plate, count

    def to_result_dict(self) -> Optional[dict]:
        raw, vc = self.best_vote()
        if not raw:
            return None
        norm = normalize_israeli_private_plate(raw)
        if not norm:
            return None
        return {
            "track_id": self.track_id,
            "raw_digits": raw,
            "normalized_plate": norm,
            "vote_count": vc,
        }


class MultiPlateTracker:
    """Greedy IOU assignment of detections to stable track_ids."""

    def __init__(
        self,
        iou_match_threshold: float = 0.25,
        max_misses: int = 8,
        smoothing_alpha: float = 0.65,
    ):
        self.iou_match_threshold = iou_match_threshold
        self.max_misses = max_misses
        self.smoothing_alpha = smoothing_alpha
        self._next_id = 1
        self.tracks: dict[int, PlateTrackState] = {}
        self.completed: list[PlateTrackState] = []

    def _new_track(self, bbox: BBoxXYXY, frame_idx: int) -> PlateTrackState:
        tid = self._next_id
        self._next_id += 1
        t = PlateTrackState(track_id=tid, bbox_xyxy=bbox, last_seen_frame=frame_idx, miss_count=0)
        self.tracks[tid] = t
        return t

    def update(self, frame_idx: int, detections: list[PlateDetectionXYXY]) -> list[PlateTrackState]:
        det_boxes = [(d.bbox, d.confidence) for d in detections]

        # Greedy: repeatedly take best IOU pair above threshold
        pairs: list[tuple[int, int, float]] = []  # (det_i, track_id, iou)
        for di in range(len(det_boxes)):
            db, _ = det_boxes[di]
            for tid in list(self.tracks.keys()):
                iou = iou_xyxy(db, self.tracks[tid].bbox_xyxy)
                if iou >= self.iou_match_threshold:
                    pairs.append((di, tid, iou))
        pairs.sort(key=lambda x: -x[2])

        matched_det: set[int] = set()
        matched_tid: set[int] = set()
        for di, tid, _ in pairs:
            if di in matched_det or tid in matched_tid:
                continue
            matched_det.add(di)
            matched_tid.add(tid)
            db, _ = det_boxes[di]
            tr = self.tracks[tid]
            tr.bbox_xyxy = smooth_xyxy(tr.bbox_xyxy, db, self.smoothing_alpha)
            tr.last_seen_frame = frame_idx
            tr.miss_count = 0

        # New tracks for unmatched detections
        for di in range(len(det_boxes)):
            if di in matched_det:
                continue
            db, _ = det_boxes[di]
            self._new_track(db, frame_idx)

        # Missed tracks
        for tid in list(self.tracks.keys()):
            if tid in matched_tid:
                continue
            tr = self.tracks[tid]
            tr.miss_count += 1
            if tr.miss_count > self.max_misses:
                self.completed.append(self.tracks.pop(tid))

        return list(self.tracks.values())

    def finalize(self) -> list[PlateTrackState]:
        """Move all active tracks to completed (end of video)."""
        for tid in list(self.tracks.keys()):
            self.completed.append(self.tracks.pop(tid))
        return self.completed

    def all_tracks_for_results(self) -> list[PlateTrackState]:
        return list(self.completed) + list(self.tracks.values())
