"""
Violation analyzer: applies Israel parking violation rules (from israel_violation_reference.json)
to sampled video frames using OpenCV-based detectors.

Decision states (from the reference spec):
  confirmed_violation   — strong evidence, still recommend human review
  suspected_violation   — likely violation but some element uncertain
  no_violation          — video shows no violation
  insufficient_evidence — cannot determine from this footage
"""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.violation.services.curb_detector import CurbDetector

# Path to the reference rules JSON (one level above backend/)
_REF_PATH = Path(__file__).resolve().parents[5] / "israel_violation_reference" / "israel_violation_reference.json"

# HSV ranges for blue-white curb (regulated/permit parking)
_BLUE_LO = np.array([95,  80,  60], dtype=np.uint8)
_BLUE_HI = np.array([135, 255, 255], dtype=np.uint8)
_WHITE_LO = np.array([0,    0, 170], dtype=np.uint8)
_WHITE_HI = np.array([180, 70, 255], dtype=np.uint8)

# HSV ranges for crosswalk (white parallel horizontal stripes)
_CROSS_WHITE_LO = np.array([0,   0, 180], dtype=np.uint8)
_CROSS_WHITE_HI = np.array([180, 40, 255], dtype=np.uint8)


@dataclass
class ViolationResult:
    rule_id: str
    title_he: str
    title_en: str
    decision_state: str          # confirmed_violation | suspected_violation | no_violation | insufficient_evidence
    confidence: float            # 0.0 – 1.0
    evidence_flags: list[str] = field(default_factory=list)
    description_he: str = ""
    description_en: str = ""
    human_review_recommended: bool = True


class ViolationAnalyzer:
    """Analyze video frames against Israeli traffic law violation rules."""

    def __init__(self):
        self._rules_by_id: dict[str, dict] = {}
        self._curb_detector = CurbDetector()
        self._load_rules()

    def _load_rules(self) -> None:
        if not _REF_PATH.exists():
            return
        try:
            with open(_REF_PATH, encoding="utf-8") as f:
                data = json.load(f)
            for rule in data.get("rules", []):
                rid = rule.get("rule_id")
                if rid:
                    self._rules_by_id[rid] = rule
        except Exception:
            pass

    def _rule(self, rule_id: str) -> dict:
        return self._rules_by_id.get(rule_id, {})

    # ------------------------------------------------------------------ #
    # Frame-level detectors                                                #
    # ------------------------------------------------------------------ #

    def _has_red_white_curb(self, frame: np.ndarray) -> bool:
        """True if a red-white curb region is visible in this frame."""
        candidates = self._curb_detector.detect(frame)
        return len(candidates) > 0 and candidates[0].score > 0.3

    def _has_blue_white_curb(self, frame: np.ndarray) -> bool:
        """True if a blue-white curb region is visible (regulated parking zone)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        blue  = cv2.inRange(hsv, _BLUE_LO, _BLUE_HI)
        white = cv2.inRange(hsv, _WHITE_LO, _WHITE_HI)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        blue  = cv2.morphologyEx(blue,  cv2.MORPH_CLOSE, k)
        white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, k)
        # Both colours must co-occur in the lower portion of the frame
        h = frame.shape[0]
        roi_blue  = blue [h // 2:, :]
        roi_white = white[h // 2:, :]
        blue_px  = int(np.count_nonzero(roi_blue))
        white_px = int(np.count_nonzero(roi_white))
        return blue_px > 300 and white_px > 300

    def _has_crosswalk(self, frame: np.ndarray) -> bool:
        """
        Detect a pedestrian crosswalk (parallel white horizontal stripes).
        Looks for several thin horizontal white regions with regular spacing.
        """
        h, w = frame.shape[:2]
        roi = frame[h // 2:, :]          # lower half only
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, _CROSS_WHITE_LO, _CROSS_WHITE_HI)
        # Row-wise sum: crosswalk stripes give alternating high/low rows
        row_sums = mask.sum(axis=1) / 255
        threshold = w * 0.25             # at least 25% of row must be white
        white_rows = row_sums > threshold
        # Count sign-changes (stripes alternate on/off)
        transitions = int(np.diff(white_rows.astype(int)).sum())
        return transitions >= 4          # at least 2 stripes = 4 edges

    def _is_stationary(self, frames: list[np.ndarray]) -> bool:
        """
        Check whether the video shows a parked/stopped vehicle (minimal motion).
        Compares background difference between first and last sampled frame.
        Returns True when the scene is largely static.
        """
        if len(frames) < 2:
            return True
        f1 = cv2.cvtColor(frames[0],  cv2.COLOR_BGR2GRAY)
        f2 = cv2.cvtColor(frames[-1], cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(f1, f2)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        changed = np.count_nonzero(thresh)
        total   = thresh.size
        # < 15% changed pixels → largely static scene → vehicle is parked
        return (changed / total) < 0.15

    def _has_yellow_plate(self, frame: np.ndarray) -> bool:
        """Detect yellow license plate (proxy for vehicle presence)."""
        from app.services.video_processor import detect_plate_box
        return detect_plate_box(frame) is not None

    # ------------------------------------------------------------------ #
    # Frame sampling                                                       #
    # ------------------------------------------------------------------ #

    def _sample_frames(self, video_bytes: bytes, count: int = 12) -> list[np.ndarray]:
        frames: list[np.ndarray] = []
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(video_bytes)
            path = f.name
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return frames
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            step  = max(1, total // (count + 1)) if total > 0 else 1
            for i in range(count):
                idx = step * (i + 1)
                if idx >= total > 0:
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, fr = cap.read()
                if ok:
                    frames.append(fr)
            cap.release()
        finally:
            Path(path).unlink(missing_ok=True)
        return frames

    # ------------------------------------------------------------------ #
    # Rule evaluation                                                      #
    # ------------------------------------------------------------------ #

    def _eval_static_001(self, rw_count: int, n_frames: int, is_parked: bool, zone_hint: str) -> Optional[ViolationResult]:
        """IL-STATIC-001: Red-white curb prohibition zone."""
        rule = self._rule("IL-STATIC-001")
        if not rule:
            return None
        rw_ratio = rw_count / max(1, n_frames)
        if rw_ratio < 0.2 and zone_hint != "red_white":
            return None
        evidence = []
        conf = 0.0
        if rw_ratio >= 0.5:
            conf += 0.55
            evidence.append(f"red_white_curb_visible_in_{rw_count}/{n_frames}_frames")
        elif rw_ratio >= 0.2:
            conf += 0.35
            evidence.append("red_white_curb_faintly_visible")
        if zone_hint == "red_white":
            conf += 0.25
            evidence.append("reporter_confirmed_red_white_zone")
        if is_parked:
            conf += 0.15
            evidence.append("vehicle_appears_stationary")
        conf = min(conf, 0.95)
        decision = "suspected_violation" if conf < 0.75 else "confirmed_violation"
        return ViolationResult(
            rule_id="IL-STATIC-001",
            title_he=rule.get("title_he", "עצירה/חניה באזור אדום-לבן"),
            title_en=rule.get("title_en", "Stopping/parking in red-white prohibition zone"),
            decision_state=decision,
            confidence=round(conf, 2),
            evidence_flags=evidence,
            description_he=f"זוהתה חניה/עצירה באזור מסומן באבני שפה אדום-לבן (אסורה חניה).",
            description_en="Vehicle detected stopped/parked in red-white curb prohibition zone.",
        )

    def _eval_static_002(self, bw_count: int, n_frames: int, is_parked: bool, zone_hint: str) -> Optional[ViolationResult]:
        """IL-STATIC-002: Blue-white regulated parking zone."""
        rule = self._rule("IL-STATIC-002")
        if not rule:
            return None
        bw_ratio = bw_count / max(1, n_frames)
        if bw_ratio < 0.2 and zone_hint != "blue_white":
            return None
        evidence = []
        conf = 0.0
        if bw_ratio >= 0.5:
            conf += 0.40
            evidence.append(f"blue_white_curb_visible_in_{bw_count}/{n_frames}_frames")
        elif bw_ratio >= 0.2:
            conf += 0.25
            evidence.append("blue_white_curb_faintly_visible")
        if zone_hint == "blue_white":
            conf += 0.25
            evidence.append("reporter_confirmed_blue_white_zone")
        if is_parked:
            conf += 0.10
            evidence.append("vehicle_appears_stationary")
        conf = min(conf, 0.75)   # always suspected — payment status unknown
        return ViolationResult(
            rule_id="IL-STATIC-002",
            title_he=rule.get("title_he", "חניה באזור כחול-לבן ללא תשלום/היתר"),
            title_en=rule.get("title_en", "Parking in blue-white zone without payment/permit"),
            decision_state="suspected_violation",
            confidence=round(conf, 2),
            evidence_flags=evidence + ["payment_and_permit_status_unknown"],
            description_he="זוהתה חניה באזור מסומן כחול-לבן. יש לוודא אם בוצע תשלום או קיים היתר תקף.",
            description_en="Vehicle parked in blue-white regulated zone. Payment/permit status requires external verification.",
        )

    def _eval_static_013(self, crosswalk_seen: bool, is_parked: bool) -> Optional[ViolationResult]:
        """IL-STATIC-013: Parking too close to a crosswalk."""
        if not crosswalk_seen or not is_parked:
            return None
        rule = self._rule("IL-STATIC-013")
        return ViolationResult(
            rule_id="IL-STATIC-013",
            title_he=rule.get("title_he", "חניה בקרבת מעבר חציה באופן אסור") if rule else "חניה בקרבת מעבר חציה",
            title_en=rule.get("title_en", "Parking too close to a crosswalk") if rule else "Parking near crosswalk",
            decision_state="suspected_violation",
            confidence=0.45,
            evidence_flags=["crosswalk_detected_in_frame", "vehicle_appears_stationary", "distance_not_measured"],
            description_he="זוהה מעבר חציה בסמיכות לחניית הרכב. דרוש מדידת מרחק לאימות.",
            description_en="Crosswalk detected near parked vehicle. Distance measurement required to confirm violation.",
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        video_bytes: bytes,
        violation_zone: Optional[str] = None,
    ) -> ViolationResult:
        """
        Analyze video and return the best-matching violation result.
        violation_zone: reporter-supplied hint ('red_white' | 'blue_white' | None)
        """
        frames = self._sample_frames(video_bytes, count=12)
        if not frames:
            return ViolationResult(
                rule_id="",
                title_he="לא ניתן לנתח",
                title_en="Video could not be analyzed",
                decision_state="insufficient_evidence",
                confidence=0.0,
                evidence_flags=["no_frames_decoded"],
                description_he="לא ניתן היה לנתח את הוידאו.",
                description_en="Video could not be processed for violation analysis.",
            )

        n = len(frames)
        rw_count  = sum(1 for f in frames if self._has_red_white_curb(f))
        bw_count  = sum(1 for f in frames if self._has_blue_white_curb(f))
        crosswalk = any(self._has_crosswalk(f) for f in frames)
        is_parked = self._is_stationary(frames)

        zone_hint = (violation_zone or "").strip().lower()

        # Evaluate candidate rules; pick highest confidence
        candidates: list[ViolationResult] = []
        for ev in [
            self._eval_static_001(rw_count, n, is_parked, zone_hint),
            self._eval_static_002(bw_count, n, is_parked, zone_hint),
            self._eval_static_013(crosswalk, is_parked),
        ]:
            if ev is not None:
                candidates.append(ev)

        if not candidates:
            # Vehicle moving through a zone → likely no static violation
            if not is_parked:
                return ViolationResult(
                    rule_id="",
                    title_he="רכב נע — לא זוהתה חניה",
                    title_en="Moving vehicle — no parking violation detected",
                    decision_state="no_violation",
                    confidence=0.7,
                    evidence_flags=["vehicle_appears_to_be_moving"],
                    description_he="הרכב נמצא בתנועה בשלב הצילום. לא זוהתה חניה אסורה.",
                    description_en="Vehicle appears to be moving. No parking violation detected.",
                )
            return ViolationResult(
                rule_id="",
                title_he="אין מספיק עדויות",
                title_en="Insufficient evidence",
                decision_state="insufficient_evidence",
                confidence=0.0,
                evidence_flags=["no_curb_marking_detected", "no_zone_hint"],
                description_he="לא ניתן לקבוע הפרה על בסיס המידע הזמין בוידאו.",
                description_en="Could not determine a violation from the available video evidence.",
            )

        best = max(candidates, key=lambda r: r.confidence)
        print(
            f"[ViolationAnalyzer] rule={best.rule_id} state={best.decision_state} "
            f"conf={best.confidence:.2f} evidence={best.evidence_flags}"
        )
        return best
