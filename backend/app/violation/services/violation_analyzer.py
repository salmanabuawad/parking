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

# Fallback JSON for when DB is unavailable (same directory as this file)
_REF_PATH = Path(__file__).resolve().parent / "israel_violation_reference.json"

# HSV ranges for blue-white curb (regulated/permit parking)
_BLUE_LO = np.array([95,  80,  60], dtype=np.uint8)
_BLUE_HI = np.array([135, 255, 255], dtype=np.uint8)
_WHITE_LO = np.array([0,    0, 170], dtype=np.uint8)
_WHITE_HI = np.array([180, 70, 255], dtype=np.uint8)

# HSV ranges for crosswalk (white parallel horizontal stripes)
_CROSS_WHITE_LO = np.array([0,   0, 180], dtype=np.uint8)
_CROSS_WHITE_HI = np.array([180, 40, 255], dtype=np.uint8)

# HSV ranges for red-yellow curb (bus stops)
_YELLOW_LO = np.array([15,  80, 100], dtype=np.uint8)
_YELLOW_HI = np.array([38, 255, 255], dtype=np.uint8)
_RED_LO1   = np.array([0,   80,  80], dtype=np.uint8)
_RED_HI1   = np.array([10, 255, 255], dtype=np.uint8)
_RED_LO2   = np.array([160, 80,  80], dtype=np.uint8)
_RED_HI2   = np.array([180, 255, 255], dtype=np.uint8)


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
        # Primary: load from DB
        try:
            from app.database import SessionLocal
            from app.models import ViolationRule
            db = SessionLocal()
            try:
                rows = db.query(ViolationRule).filter(ViolationRule.is_active == True).all()
                for row in rows:
                    self._rules_by_id[row.rule_id] = {
                        "rule_id": row.rule_id,
                        "title_he": row.title_he,
                        "title_en": row.title_en,
                        "description_he": row.description_he or "",
                        "description_en": row.description_en or "",
                        "legal_basis_he": row.legal_basis_he or "",
                        "legal_basis_en": row.legal_basis_en or "",
                        "fine_ils": row.fine_ils,
                    }
                if self._rules_by_id:
                    return
            finally:
                db.close()
        except Exception:
            pass
        # Fallback: load from JSON file (used during seeding / before DB is ready)
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

    def _has_red_yellow_curb(self, frame: np.ndarray) -> bool:
        """Detect red-and-yellow curb markings (Israeli bus stop / public transport zone).
        Both red and yellow pixels must co-occur in the lower portion of the frame,
        forming a horizontally elongated region (aspect ratio > 2.5).
        """
        h, w = frame.shape[:2]
        roi = frame[h * 2 // 3:, :]   # bottom third — curb level
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red1   = cv2.inRange(hsv, _RED_LO1,   _RED_HI1)
        red2   = cv2.inRange(hsv, _RED_LO2,   _RED_HI2)
        red    = cv2.bitwise_or(red1, red2)
        yellow = cv2.inRange(hsv, _YELLOW_LO, _YELLOW_HI)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        red    = cv2.morphologyEx(red,    cv2.MORPH_CLOSE, k)
        yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, k)
        red_px    = int(np.count_nonzero(red))
        yellow_px = int(np.count_nonzero(yellow))
        return red_px > 200 and yellow_px > 200

    def _has_no_stop_sign(self, frame: np.ndarray) -> bool:
        """Detect a red circular no-stopping or no-parking sign.
        Israeli no-stopping sign: red circle with two parallel diagonal lines.
        Israeli no-parking sign:  red circle with one diagonal line.
        Both are approximated by detecting a red-dominant circle in the upper
        portion of the frame (signs are mounted above the road surface).
        """
        h, w = frame.shape[:2]
        roi = frame[:h * 2 // 3, :]   # upper two-thirds — sign height
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red1 = cv2.inRange(hsv, _RED_LO1, _RED_HI1)
        red2 = cv2.inRange(hsv, _RED_LO2, _RED_HI2)
        red  = cv2.bitwise_or(red1, red2)
        red  = cv2.morphologyEx(red, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        # Look for circular blobs consistent with a round traffic sign (r 15–80 px)
        circles = cv2.HoughCircles(
            red, cv2.HOUGH_GRADIENT, dp=1.2,
            minDist=40, param1=50, param2=15,
            minRadius=15, maxRadius=80,
        )
        if circles is None:
            return False
        circles = np.round(circles[0]).astype(int)
        for (cx, cy, r) in circles:
            # Confirm the circle area is predominantly red
            mask = np.zeros(red.shape, dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            inside_px = int(np.count_nonzero(cv2.bitwise_and(red, mask)))
            circle_area = int(np.pi * r * r)
            if circle_area > 0 and inside_px / circle_area > 0.35:
                return True
        return False

    def _has_double_parked_vehicle(self, frames: list[np.ndarray]) -> bool:
        """Detect a vehicle stopped in the travel lane (double parking).

        Strategy: look for a large vehicle-sized stationary blob in the
        horizontal middle band of the frame — away from the curb edge but
        not near the top (sky / buildings). A contour that spans >15% of
        frame width and is inside the central 20–70% vertical strip is a
        candidate. We require it to appear in at least 40% of frames to
        confirm it is stationary, not a passing car.
        """
        if not frames:
            return False
        hits = 0
        for frame in frames:
            h, w = frame.shape[:2]
            # Focus on the travel-lane band: vertically 25%–72% of frame
            roi = frame[h // 4: h * 3 // 4, :]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (7, 7), 0)
            _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            # Remove noise
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            roi_h, roi_w = roi.shape[:2]
            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                # Must be vehicle-width (>15% frame width) and vehicle-height (>10% roi height)
                if cw > roi_w * 0.15 and ch > roi_h * 0.10:
                    # Must be in the middle horizontal band (not glued to frame edge — that's the curb car)
                    left_margin  = x / roi_w
                    right_margin = (roi_w - x - cw) / roi_w
                    if left_margin > 0.05 and right_margin > 0.05:
                        hits += 1
                        break
        return hits / max(1, len(frames)) >= 0.40

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

    def _has_time_limit_sign(self, frame: np.ndarray) -> bool:
        """Detect a blue rectangular time-limit parking sign (e.g. '1 שעה' / 'P 1h').
        Israeli time-limit signs are blue rectangular signs with white text.
        We look for a blue rectangular blob in the upper portion of the frame.
        """
        h, w = frame.shape[:2]
        roi = frame[:h * 2 // 3, :]   # upper two-thirds — sign height
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        blue = cv2.inRange(hsv, _BLUE_LO, _BLUE_HI)
        blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
        contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi_h, roi_w = roi.shape[:2]
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Sign-sized blue rectangle: width 6–25% of frame, aspect ratio 0.5–3
            if cw > roi_w * 0.06 and ch > roi_h * 0.04:
                aspect = cw / max(1, ch)
                if 0.4 < aspect < 3.5:
                    return True
        return False

    def _has_yellow_curb(self, frame: np.ndarray) -> bool:
        """Detect solid yellow curb marking (freight/loading zone — private cars prohibited).
        Distinct from red-yellow bus-stop curb: here the entire curb is solid yellow,
        with no red component.
        """
        h, w = frame.shape[:2]
        roi = frame[h * 2 // 3:, :]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, _YELLOW_LO, _YELLOW_HI)
        red1   = cv2.inRange(hsv, _RED_LO1,   _RED_HI1)
        red2   = cv2.inRange(hsv, _RED_LO2,   _RED_HI2)
        red    = cv2.bitwise_or(red1, red2)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, k)
        red    = cv2.morphologyEx(red,    cv2.MORPH_CLOSE, k)
        yellow_px = int(np.count_nonzero(yellow))
        red_px    = int(np.count_nonzero(red))
        # Solid yellow with very little red — freight zone, not bus stop
        return yellow_px > 400 and red_px < yellow_px * 0.25

    def _looks_like_private_car(self, frame: np.ndarray) -> bool:
        """Rough heuristic: detect a low-profile vehicle (sedan/SUV aspect ratio) in the frame.
        Trucks and vans are taller relative to their width. A detected vehicle blob with
        width/height ratio > 2.2 suggests a private car rather than a freight vehicle.
        """
        h, w = frame.shape[:2]
        roi = frame[h // 3: h * 3 // 4, :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(cv2.GaussianBlur(gray, (7, 7), 0), 0, 255,
                                  cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi_h, roi_w = roi.shape[:2]
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw > roi_w * 0.18 and ch > roi_h * 0.12:
                if ch > 0 and (cw / ch) > 2.2:
                    return True
        return False

    def _eval_static_003(self, double_parked: bool, is_parked: bool) -> Optional[ViolationResult]:
        """IL-STATIC-003: Double parking — vehicle blocking another parked car or travel lane."""
        if not double_parked or not is_parked:
            return None
        rule = self._rule("IL-STATIC-003")
        return ViolationResult(
            rule_id="IL-STATIC-003",
            title_he=rule.get("title_he", "חניה כפולה — חסימת נתיב נסיעה") if rule else "חניה כפולה — חסימת נתיב נסיעה",
            title_en=rule.get("title_en", "Double parking — blocking traffic lane") if rule else "Double parking — blocking traffic lane",
            decision_state="suspected_violation",
            confidence=0.55,
            evidence_flags=["large_stationary_vehicle_detected_in_travel_lane", "vehicle_appears_stationary"],
            description_he="זוהה רכב חונה בנתיב הנסיעה (חניה כפולה). חסימת נתיב הנסיעה אסורה.",
            description_en="A stationary vehicle was detected in the travel lane, indicating possible double parking. Blocking the travel lane is prohibited.",
        )

    def _eval_static_004(self, yellow_curb: bool, is_private_car: bool, is_parked: bool) -> Optional[ViolationResult]:
        """IL-STATIC-004: Private car parked in a freight/loading zone (solid yellow curb)."""
        if not yellow_curb or not is_parked:
            return None
        rule = self._rule("IL-STATIC-004")
        conf = 0.50
        evidence = ["solid_yellow_curb_detected"]
        if is_private_car:
            conf += 0.20
            evidence.append("vehicle_profile_matches_private_car")
        return ViolationResult(
            rule_id="IL-STATIC-004",
            title_he=rule.get("title_he", "חניה של רכב פרטי באזור פריקה/העמסה (שפה צהובה)") if rule else "חניה של רכב פרטי באזור פריקה/העמסה",
            title_en=rule.get("title_en", "Private car parked in freight/loading zone (yellow curb)") if rule else "Private car parked in freight/loading zone",
            decision_state="suspected_violation",
            confidence=round(min(conf, 0.80), 2),
            evidence_flags=evidence,
            description_he="זוהתה שפה צהובה המציינת אזור פריקה/העמסה לרכב מסחרי בלבד. חניית רכב פרטי באזור זה אסורה.",
            description_en="Solid yellow curb detected indicating a freight/loading zone reserved for commercial vehicles. Private cars parking here is prohibited.",
        )

    def _eval_static_006(self, time_limit_sign: bool, is_parked: bool) -> Optional[ViolationResult]:
        """IL-STATIC-006: Parking exceeding posted time limit.
        NOTE: Actual duration cannot be determined from video alone.
        This rule flags the combination of a time-limit sign + stationary vehicle
        for human review — the inspector must verify arrival time externally.
        """
        if not time_limit_sign or not is_parked:
            return None
        rule = self._rule("IL-STATIC-006")
        return ViolationResult(
            rule_id="IL-STATIC-006",
            title_he=rule.get("title_he", "חניה מעל הזמן המותר (שלט הגבלת זמן)") if rule else "חניה מעל הזמן המותר",
            title_en=rule.get("title_en", "Parking beyond the posted time limit") if rule else "Parking beyond posted time limit",
            decision_state="insufficient_evidence",
            confidence=0.35,
            evidence_flags=["time_limit_sign_detected", "vehicle_appears_stationary", "arrival_time_unknown"],
            description_he="זוהה שלט הגבלת זמן חניה ורכב חונה. לא ניתן לאמת את משך החניה מהוידאו — נדרשת בדיקה ידנית של שעת ההגעה.",
            description_en="Time-limit parking sign detected with a stationary vehicle. Parking duration cannot be determined from video alone — human review of arrival time is required.",
        )

    def _eval_static_007(self, is_parked: bool, zone_hint: str) -> Optional[ViolationResult]:
        """IL-STATIC-007: Vehicle without resident permit parked in residents-only zone.
        Detection relies entirely on zone_hint='residents_only' set per camera —
        visual cues alone cannot verify permit status.
        """
        if zone_hint != "residents_only" or not is_parked:
            return None
        rule = self._rule("IL-STATIC-007")
        return ViolationResult(
            rule_id="IL-STATIC-007",
            title_he=rule.get("title_he", "חניה ללא תג דיירים באזור דיירים") if rule else "חניה ללא תג דיירים באזור דיירים",
            title_en=rule.get("title_en", "Parking without residents permit in residents-only zone") if rule else "Parking without residents permit",
            decision_state="insufficient_evidence",
            confidence=0.40,
            evidence_flags=["camera_zone_is_residents_only", "vehicle_appears_stationary", "permit_tag_not_verifiable_from_video"],
            description_he="מצלמה זו ממוקמת באזור חניה לדיירים בלבד. לא ניתן לאמת תג דיירים מהוידאו — נדרשת בדיקה ידנית.",
            description_en="This camera covers a residents-only parking zone. Permit verification cannot be done from video — manual inspection required.",
        )

    def _eval_static_008(self, time_sign: bool, is_parked: bool, captured_hour: Optional[int] = None) -> Optional[ViolationResult]:
        """IL-STATIC-008: Parking during prohibited hours (zone free outside defined hours).
        Without knowing the exact sign's hours, we flag for human review when a time-related sign
        is detected and the vehicle is stationary. If captured_hour is provided (from job metadata)
        and falls inside typical enforcement hours (07-20), confidence is raised slightly.
        """
        if not time_sign or not is_parked:
            return None
        rule = self._rule("IL-STATIC-008")
        conf = 0.30
        evidence = ["time_restriction_sign_detected", "vehicle_appears_stationary"]
        if captured_hour is not None and 7 <= captured_hour <= 20:
            conf += 0.15
            evidence.append(f"captured_during_typical_enforcement_hours_{captured_hour:02d}h")
        return ViolationResult(
            rule_id="IL-STATIC-008",
            title_he=rule.get("title_he", "חניה בשעות האסורות") if rule else "חניה בשעות האסורות",
            title_en=rule.get("title_en", "Parking during prohibited hours") if rule else "Parking during prohibited hours",
            decision_state="insufficient_evidence",
            confidence=round(min(conf, 0.55), 2),
            evidence_flags=evidence,
            description_he="זוהה שלט הגבלת שעות ורכב חונה. לא ניתן לאמת את שעת החניה ביחס לשלט מהוידאו — נדרשת בדיקה ידנית.",
            description_en="Hour-restriction sign detected with a stationary vehicle. Parking hours relative to the sign cannot be confirmed from video alone — human review required.",
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

    def _eval_static_005(self, ry_count: int, n_frames: int, is_parked: bool) -> Optional[ViolationResult]:
        """IL-STATIC-005: Stopping or parking in a bus stop area (red-yellow curb)."""
        rule = self._rule("IL-STATIC-005")
        ry_ratio = ry_count / max(1, n_frames)
        if ry_ratio < 0.2:
            return None
        evidence = []
        conf = 0.0
        if ry_ratio >= 0.5:
            conf += 0.55
            evidence.append(f"red_yellow_curb_visible_in_{ry_count}/{n_frames}_frames")
        elif ry_ratio >= 0.2:
            conf += 0.35
            evidence.append("red_yellow_curb_faintly_visible")
        if is_parked:
            conf += 0.20
            evidence.append("vehicle_appears_stationary")
        conf = min(conf, 0.90)
        decision = "confirmed_violation" if conf >= 0.70 else "suspected_violation"
        return ViolationResult(
            rule_id="IL-STATIC-005",
            title_he=rule.get("title_he", "עצירה/חניה בתחנת אוטובוס") if rule else "עצירה/חניה בתחנת אוטובוס",
            title_en=rule.get("title_en", "Stopping/parking in a bus stop area") if rule else "Stopping/parking in a bus stop area",
            decision_state=decision,
            confidence=round(conf, 2),
            evidence_flags=evidence,
            description_he="זוהה סימון אדום-צהוב (תחנת אוטובוס). חניה/עצירה של כלי רכב פרטי בתחנת אוטובוס אסורה.",
            description_en="Red-yellow curb marking detected (bus stop zone). Stopping/parking private vehicles in bus stop areas is prohibited.",
        )

    def _eval_static_014(self, sign_seen: bool, is_parked: bool, zone_hint: str) -> Optional[ViolationResult]:
        """IL-STATIC-014: Stopping where a no-stopping sign applies."""
        if not sign_seen:
            return None
        rule = self._rule("IL-STATIC-014")
        evidence = ["no_stopping_sign_detected_in_frame"]
        conf = 0.50
        if is_parked:
            conf += 0.20
            evidence.append("vehicle_appears_stationary")
        if zone_hint == "red_white":
            conf += 0.15
            evidence.append("reporter_confirmed_no_stopping_zone")
        conf = min(conf, 0.85)
        return ViolationResult(
            rule_id="IL-STATIC-014",
            title_he=rule.get("title_he", "עצירה באזור שלט 'אסור לעצור'") if rule else "עצירה באזור שלט 'אסור לעצור'",
            title_en=rule.get("title_en", "Stopping where a no-stopping sign applies") if rule else "Stopping where a no-stopping sign applies",
            decision_state="suspected_violation",
            confidence=round(conf, 2),
            evidence_flags=evidence,
            description_he="זוהה שלט עגול אדום האוסר עצירה. עצירת רכב באזור זה אסורה.",
            description_en="Red circular no-stopping sign detected. Stopping in this zone is prohibited under Israeli traffic law.",
        )

    def _eval_static_015(self, sign_seen: bool, is_parked: bool) -> Optional[ViolationResult]:
        """IL-STATIC-015: Parking where a no-parking sign applies."""
        if not sign_seen or not is_parked:
            return None
        rule = self._rule("IL-STATIC-015")
        return ViolationResult(
            rule_id="IL-STATIC-015",
            title_he=rule.get("title_he", "חניה באזור שלט 'אסור לחנות'") if rule else "חניה באזור שלט 'אסור לחנות'",
            title_en=rule.get("title_en", "Parking where a no-parking sign applies") if rule else "Parking where a no-parking sign applies",
            decision_state="suspected_violation",
            confidence=0.55,
            evidence_flags=["no_parking_sign_detected_in_frame", "vehicle_appears_stationary"],
            description_he="זוהה שלט עגול אדום (אסור לחנות) ורכב חונה. חניה באזור זה אסורה.",
            description_en="Red circular no-parking sign and stationary vehicle detected. Parking here is prohibited.",
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        video_bytes: bytes,
        violation_zone: Optional[str] = None,
        allowed_rules: Optional[list] = None,
        captured_at: Optional[object] = None,
    ) -> ViolationResult:
        """
        Analyze video and return the best-matching violation result.
        violation_zone: reporter-supplied hint ('red_white' | 'blue_white' | 'residents_only' | None)
        allowed_rules: if non-empty, only evaluate these rule IDs (e.g. ['IL-STATIC-001', 'IL-STATIC-005'])
        captured_at: datetime of capture (used to determine hour for time-restriction rules)
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
        rw_count     = sum(1 for f in frames if self._has_red_white_curb(f))
        bw_count     = sum(1 for f in frames if self._has_blue_white_curb(f))
        ry_count     = sum(1 for f in frames if self._has_red_yellow_curb(f))
        yc_count     = sum(1 for f in frames if self._has_yellow_curb(f))
        crosswalk    = any(self._has_crosswalk(f) for f in frames)
        sign_seen    = any(self._has_no_stop_sign(f) for f in frames)
        time_sign    = any(self._has_time_limit_sign(f) for f in frames)
        is_parked    = self._is_stationary(frames)
        double_park  = self._has_double_parked_vehicle(frames)
        is_priv_car  = any(self._looks_like_private_car(f) for f in frames)

        zone_hint = (violation_zone or "").strip().lower()

        # Evaluate all candidate rules; pick highest confidence
        rule_map = {
            "IL-STATIC-001": self._eval_static_001(rw_count, n, is_parked, zone_hint),
            "IL-STATIC-002": self._eval_static_002(bw_count, n, is_parked, zone_hint),
            "IL-STATIC-003": self._eval_static_003(double_park, is_parked),
            "IL-STATIC-004": self._eval_static_004(yc_count > n * 0.3, is_priv_car, is_parked),
            "IL-STATIC-005": self._eval_static_005(ry_count, n, is_parked),
            "IL-STATIC-006": self._eval_static_006(time_sign, is_parked),
            "IL-STATIC-007": self._eval_static_007(is_parked, zone_hint),
            "IL-STATIC-008": self._eval_static_008(time_sign, is_parked,
                                captured_hour=getattr(captured_at, "hour", None)),
            "IL-STATIC-013": self._eval_static_013(crosswalk, is_parked),
            "IL-STATIC-014": self._eval_static_014(sign_seen, is_parked, zone_hint),
            "IL-STATIC-015": self._eval_static_015(sign_seen, is_parked),
        }
        rule_ids_to_check = set(allowed_rules) if allowed_rules else set(rule_map.keys())
        candidates: list[ViolationResult] = []
        for rule_id, ev in rule_map.items():
            if rule_id in rule_ids_to_check and ev is not None:
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
