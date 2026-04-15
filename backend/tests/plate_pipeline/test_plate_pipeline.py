"""
Tests for Israeli plate-processing pipeline modules.
Per spec: yellow mask, contour filtering, tracker reuse, OCR vote, registry, plate format, blur.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

# Add backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent))

from app.plate_pipeline.anpr_multi import (
    MultiPlateTracker,
    PlateDetectionXYXY,
    iou_xyxy,
    normalize_israeli_private_plate,
)
from app.plate_pipeline.blur_pipeline import blur_except_plate, blur_frame
from app.plate_pipeline.config import PLATE_MAX_RATIO, PLATE_MIN_RATIO
from app.plate_pipeline.plate_detector import PlateDetector, _hsv_detect_plates
from app.plate_pipeline.plate_format import classify_plate_format
from app.plate_pipeline.ocr_vote import OCRVote
from app.plate_pipeline.registry_lookup import RegistryLookup, normalize_plate
from app.plate_pipeline.tracker import PlateTracker


# --- Yellow mask generation ---
def test_yellow_mask_generation():
    """HSV yellow plate detection: yellow rectangle should produce mask and be detected."""
    # Create BGR image with yellow rectangle (Israeli plate color).
    # Pure BGR yellow (0,255,255) -> HSV (30,255,255). Must satisfy:
    # area >= 200, ratio 1.5-7.0, area <= 0.12 * frame_area.
    h, w = 200, 400  # frame 80000; max plate area 9600
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[80:110, 150:300] = (0, 255, 255)  # 150x30 rect, area=4500, ratio=5.0
    boxes = _hsv_detect_plates(frame)
    assert len(boxes) >= 1, "Yellow rectangle should be detected as plate candidate"
    (x, y, bw, bh), conf = boxes[0]
    assert bw > 50
    assert bh > 20
    assert 0 < conf <= 1.0


# --- Plate contour filtering ---
def test_motorcycle_aspect_yellow_plate_detected():
    """HSV path must accept Israeli motorcycle-like aspect (~17/16), not only wide car plates."""
    h, w = 200, 400
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # ~85x80 BGR yellow → ratio width/height ≈ 1.06 (17 cm / 16 cm plate)
    frame[60:140, 160:245] = (0, 255, 255)
    boxes = _hsv_detect_plates(frame)
    assert boxes, "motorcycle-shaped yellow plate should produce a candidate"
    (_, _, bw, bh), _ = boxes[0]
    assert bh > 0
    assert PLATE_MIN_RATIO <= (bw / bh) <= PLATE_MAX_RATIO


def test_plate_contour_filtering():
    """Contours that don't meet ratio/area should be filtered out."""
    # Create frame with very tall narrow blob (not plate-like) and valid plate
    h, w = 200, 400
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # Tall narrow stripe - should be filtered (ratio too extreme)
    frame[10:190, 100:115] = (0, 220, 255)
    # Valid plate-like rectangle (ratio within configured band; was 120x15 => 8.0, over PLATE_MAX_RATIO)
    frame[80:95, 200:275] = (0, 220, 255)
    boxes = _hsv_detect_plates(frame)
    assert boxes, "expected at least one plate-like contour"
    # Tall stripe filtered by PLATE_MIN_RATIO / PLATE_MAX_RATIO
    for (_, _, bw, bh), _ in boxes:
        ratio = bw / bh if bh > 0 else 0
        assert PLATE_MIN_RATIO <= ratio <= PLATE_MAX_RATIO


def test_plate_contour_filtering_small_area():
    """Very small contours should be filtered by MIN_PLATE_AREA."""
    h, w = 100, 200
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[40:45, 80:90] = (0, 220, 255)  # Tiny 5x10 = 50 px
    boxes = _hsv_detect_plates(frame)
    # Area 50 < MIN_PLATE_AREA (200), should not appear
    for (bx, by, bw, bh), _ in boxes:
        assert bw * bh >= 200


# --- Tracker reuse on missing frames ---
def test_tracker_reuse_on_missing_frames():
    """Tracker should reuse last good box for limited frames when detector misses."""
    tracker = PlateTracker(max_misses=3, alpha=0.5)
    box1 = (100, 100, 200, 40)
    assert tracker.update(box1) == box1
    # Miss several frames
    for _ in range(2):
        out = tracker.update(None)
        assert out == box1
    # One more miss: still within max_misses=3
    assert tracker.update(None) == box1
    # Fourth miss: should lose track
    assert tracker.update(None) is None


def test_tracker_smoothing():
    """Tracker should smooth box coordinates over time."""
    tracker = PlateTracker(max_misses=10, alpha=0.5)
    b1 = (100, 100, 200, 40)
    b2 = (110, 105, 205, 42)
    tracker.update(b1)
    out = tracker.update(b2)
    # Smoothed: ~0.5*b2 + 0.5*b1
    assert 100 <= out[0] <= 110
    assert 100 <= out[1] <= 105
    assert 200 <= out[2] <= 205
    assert 40 <= out[3] <= 42


# --- OCR vote: most frequent valid candidate ---
def test_ocr_vote_most_frequent_valid():
    """best_valid returns most frequent candidate that exists in registry."""
    vote = OCRVote()
    vote.add("1234567")  # 1
    vote.add("7654321")  # 1
    vote.add("7654321")  # 2
    vote.add("7654321")  # 3
    vote.add("1111111")  # 1
    # Registry only has 7654321 and 1111111
    registry = lambda p: p in ("7654321", "1111111")
    assert vote.best_valid(registry) == "7654321"


def test_ocr_vote_no_valid_returns_none():
    """best_valid returns None when no candidate exists in registry."""
    vote = OCRVote()
    vote.add("1234567")
    vote.add("1234567")
    registry = lambda p: False
    assert vote.best_valid(registry) is None


def test_ocr_vote_skips_non_plausible():
    """Only 7-8 digit candidates are accepted."""
    vote = OCRVote()
    vote.add("123")      # too short
    vote.add("12345678901")  # too long
    vote.add("1234567")  # valid
    assert vote.all_candidates() == [("1234567", 1)]


# --- Registry lookup normalization ---
def test_registry_lookup_normalization(tmp_path):
    """Registry normalizes MISPAR_RECHEV to digits only."""
    csv_path = tmp_path / "registry.csv"
    csv_path.write_text("MISPAR_RECHEV,TOZERET_NM\n12-345-67,TOYOTA\n87654321,HONDA\n")
    r = RegistryLookup(csv_path)
    assert r.exists("12-345-67")
    assert r.exists("1234567")
    assert r.exists("12 34 567")
    assert r.exists("87654321")
    assert not r.exists("99999999")


def test_registry_get_returns_metadata(tmp_path):
    """get() returns manufacturer, model, year when available."""
    csv_path = tmp_path / "registry.csv"
    csv_path.write_text(
        "MISPAR_RECHEV,TOZERET_NM,KINUY_MISHARI,SHNAT_YITZUR\n"
        "1234567,TOYOTA,COROLLA,2020\n"
    )
    r = RegistryLookup(csv_path)
    row = r.get("1234567")
    assert row is not None
    assert row.get("plate") == "1234567"
    assert row.get("manufacturer") == "TOYOTA"
    assert row.get("model") == "COROLLA"
    assert row.get("year") == 2020


def test_normalize_plate():
    """normalize_plate extracts digits only."""
    assert normalize_plate("12-345-67") == "1234567"
    assert normalize_plate("ABC 123") == "123"
    assert normalize_plate("") == ""


# --- Plate format classification ---
def test_plate_format_classification():
    """classify_plate_format returns preset with width_cm, height_cm."""
    # private_long ratio ~4.33 (52/12)
    fmt = classify_plate_format(260, 60)
    assert fmt is not None
    assert fmt["name"] == "private_long"
    assert fmt["width_cm"] == 52.0
    assert fmt["height_cm"] == 12.0

    # private_rect ratio 2.0 (32/16)
    fmt2 = classify_plate_format(64, 32)
    assert fmt2 is not None
    assert fmt2["name"] == "private_rect"

    # motorcycle ratio ~1.06 (17/16)
    fmt3 = classify_plate_format(34, 32)
    assert fmt3 is not None
    assert fmt3["name"] == "motorcycle"


def test_normalize_israeli_private_plate():
    assert normalize_israeli_private_plate("1234567") == "12-345-67"
    assert normalize_israeli_private_plate("12345678") == "123-45-678"
    assert normalize_israeli_private_plate("12-345-67") == "12-345-67"
    assert normalize_israeli_private_plate("123") is None


def test_iou_xyxy_overlap():
    a = (0, 0, 100, 100)
    b = (50, 50, 150, 150)
    assert 0.0 < iou_xyxy(a, b) < 1.0
    assert iou_xyxy(a, (200, 200, 300, 300)) == 0.0


def test_multi_plate_tracker_assigns_ids():
    tr = MultiPlateTracker(iou_match_threshold=0.1, max_misses=3, smoothing_alpha=1.0)
    d1 = [PlateDetectionXYXY(bbox=(10, 10, 110, 50), confidence=0.9)]
    active = tr.update(0, d1)
    assert len(active) == 1
    assert active[0].track_id == 1
    d2 = [PlateDetectionXYXY(bbox=(12, 12, 112, 52), confidence=0.9)]
    active2 = tr.update(1, d2)
    assert len(active2) == 1
    assert active2[0].track_id == 1


def test_plate_format_zero_height():
    """classify_plate_format returns None for zero height."""
    assert classify_plate_format(100, 0) is None


# --- Blur pipeline output shape ---
def test_blur_pipeline_output_shape():
    """blur_except_plate and blur_frame preserve frame shape."""
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    blurred = blur_frame(frame)
    assert blurred.shape == frame.shape

    out_none = blur_except_plate(frame, None)
    assert out_none.shape == frame.shape

    # With plate bbox
    bbox = (100, 200, 150, 40)
    out_plate = blur_except_plate(frame, bbox)
    assert out_plate.shape == frame.shape


def test_blur_with_plate_restores_region():
    """When plate_bbox given, that region should differ from fully blurred."""
    frame = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
    out_blurred = blur_except_plate(frame, None)
    bbox = (50, 40, 80, 25)
    out_restored = blur_except_plate(frame, bbox)
    # Restored region should match original (sharp)
    x, y, w, h = bbox
    orig_roi = frame[y:y + h, x:x + w]
    restored_roi = out_restored[y:y + h, x:x + w]
    np.testing.assert_array_equal(orig_roi, restored_roi)
