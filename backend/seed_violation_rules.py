"""Seed the violation_rules table with the active Israeli violation types.

Run on the server after applying the DB migration:
  python seed_violation_rules.py

Authoritative + safe to re-run: upserts the canonical set below (INSERT ... ON CONFLICT
DO UPDATE semantics) AND force-removes any other rule. Historical tickets keep their
immutable violation_rule_snapshot, so pruning the catalog never alters past reports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import ViolationRule

RULES = [
    {
        "rule_id": "IL-STATIC-001",
        "title_he": "עצירה/חניה באזור שפה אדומה-לבנה",
        "title_en": "Stopping/parking in a red-white curb prohibition zone",
        "legal_basis_he": "תקנה 72 לתקנות התעבורה — חניה/עצירה אסורה בכל עת",
        "legal_basis_en": "Traffic Regulations §72 — stopping/parking prohibited at all times",
        "description_he": "שפה צבועה אדום-לבן מציינת איסור מוחלט לעצור או לחנות בכל עת ובכל תנאי. החל על כלל כלי הרכב ללא יוצא מן הכלל.",
        "description_en": "Red-white curb markings indicate an absolute prohibition on stopping or parking at any time. Applies to all vehicles without exception.",
        "fine_ils": 1000,
    },
    {
        "rule_id": "IL-STATIC-003",
        "title_he": "חניה כפולה — חסימת נתיב נסיעה",
        "title_en": "Double parking — blocking the traffic lane",
        "legal_basis_he": "תקנה 71(א)(1) — אסור לחנות באופן שיפריע לתנועת כלי רכב אחרים",
        "legal_basis_en": "Traffic Regulations §71(a)(1) — prohibited to park in a way that obstructs other vehicle movement",
        "description_he": "חניה כפולה היא חניית רכב לצד רכב חונה אחר, תוך חסימת נתיב הנסיעה. מהווה סכנה לתנועה ועבירה על פקודת התעבורה.",
        "description_en": "Double parking means parking alongside another parked vehicle, blocking the travel lane. This constitutes a traffic hazard and a violation of Israeli traffic law.",
        "fine_ils": 500,
    },
    {
        "rule_id": "IL-STATIC-016",
        "title_he": "שני גלגלים על המדרכה",
        "title_en": "Two wheels on sidewalk",
        "legal_basis_he": "חניה כאשר שני גלגלים או יותר נמצאים על המדרכה או בשטח הולכי רגל, לפי הוראות התמרור/חוק העזר המקומי.",
        "legal_basis_en": "Parking with two or more wheels on the sidewalk or pedestrian area, according to signage/municipal bylaw.",
        "description_he": "הרכב חונה כך ששני גלגלים נמצאים על המדרכה. יש להציג תמונה כללית, מספר רכב ברור, תחילת עבירה וסיום עבירה.",
        "description_en": "Vehicle parked with two wheels on the sidewalk. Requires context image, clear plate image, violation start and end evidence.",
        "fine_ils": 500,
        "default_min_stay_seconds": 30,
        "default_evidence_video_seconds": 20,
    },
    {
        "rule_id": "IL-STATIC-020",
        "title_he": "חניה במקום שמור לנכה ללא תג נכה בתוקף",
        "title_en": "Parking in a disabled-reserved space without a valid disabled permit",
        "legal_basis_he": "חוק חניה לנכים / תקנות התעבורה — מקום המסומן ושמור לנכה מותר לשימוש רק לבעל תג נכה בתוקף",
        "legal_basis_en": "Disabled Parking Law / Traffic Regulations — a disabled-reserved space may be used only by a holder of a valid disabled permit",
        "description_he": "הרכב חונה במקום המסומן ושמור לנכים ללא הצגת תג נכה בתוקף.",
        "description_en": "Vehicle parked in a space marked and reserved for people with disabilities without displaying a valid permit.",
        "fine_ils": 1000,
    },
]

# Semantic violation_code per rule_id (#2).
CODE_BY_RULE = {
    "IL-STATIC-001": "RED_WHITE_CURB",
    "IL-STATIC-003": "DOUBLE_PARKING",
    "IL-STATIC-016": "TWO_WHEELS_ON_SIDEWALK",
    "IL-STATIC-020": "DISABLED_PARKING",
}


def seed():
    db = SessionLocal()
    try:
        keep_ids = {r["rule_id"] for r in RULES}
        added = updated = 0
        for r in RULES:
            r.setdefault("violation_code", CODE_BY_RULE.get(r["rule_id"]))
            existing = db.query(ViolationRule).filter(ViolationRule.rule_id == r["rule_id"]).first()
            if existing:
                for k, v in r.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(ViolationRule(**r))
                added += 1
        # Force-remove any rule NOT in the canonical set. Historical tickets keep their
        # immutable violation_rule_snapshot, so this never alters past reports.
        removed = (
            db.query(ViolationRule)
            .filter(~ViolationRule.rule_id.in_(keep_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"Done: {added} added, {updated} updated, {removed} removed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
