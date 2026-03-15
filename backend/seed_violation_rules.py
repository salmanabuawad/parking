"""Seed the violation_rules table with Israeli traffic law rules.

Run once on the server after applying the DB migration:
  python seed_violation_rules.py

Safe to re-run — uses INSERT ... ON CONFLICT DO UPDATE.
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
        "rule_id": "IL-STATIC-002",
        "title_he": "חניה באזור שפה כחולה-לבנה ללא תשלום או היתר",
        "title_en": "Parking in a blue-white regulated zone without valid payment or permit",
        "legal_basis_he": "תקנה 72א — חניה בתשלום, וחוקי העיריות בדבר אזורי חניה מוסדרים",
        "legal_basis_en": "Traffic Regulations §72a — paid parking; municipal bylaws for regulated parking zones",
        "description_he": "שפה כחולה-לבנה מסמנת אזור חניה מוסדר הדורש תשלום או תג חניה תקף. חניה ללא תשלום או היתר מהווה עבירה.",
        "description_en": "Blue-white curb marks a regulated parking zone. Parking without valid payment or a permit is a violation.",
        "fine_ils": 250,
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
        "rule_id": "IL-STATIC-004",
        "title_he": "חניה של רכב פרטי באזור פריקה/העמסה (שפה צהובה)",
        "title_en": "Private car parked in a freight/loading zone (solid yellow curb)",
        "legal_basis_he": "תקנה 71(ג) — אזור פריקה/העמסה מיועד לרכב מסחרי בלבד בשעות הפעילות",
        "legal_basis_en": "Traffic Regulations §71(c) — freight/loading zones reserved for commercial vehicles during operating hours",
        "description_he": "שפה צהובה מוצקת מציינת אזור פריקה והעמסה לרכב מסחרי בלבד. חניית רכב פרטי אסורה בשעות הפעילות.",
        "description_en": "Solid yellow curb marks a freight/loading zone for commercial vehicles only. Private cars are prohibited during operating hours.",
        "fine_ils": 500,
    },
    {
        "rule_id": "IL-STATIC-005",
        "title_he": "עצירה/חניה בתחנת אוטובוס",
        "title_en": "Stopping or parking in a bus stop area",
        "legal_basis_he": "תקנה 71(ב) — אסור לעצור או לחנות במרחק של פחות מ-12 מטר לפני תחנת אוטובוס ו-6 מטר אחריה",
        "legal_basis_en": "Traffic Regulations §71(b) — prohibited within 12 m before and 6 m after a bus stop",
        "description_he": "שפה אדומה-צהובה מסמנת תחנת אוטובוס. עצירה או חניה של רכב פרטי בתחנה אסורה בהחלט.",
        "description_en": "Red-yellow curb marks a bus stop zone. Stopping or parking private vehicles here is strictly prohibited.",
        "fine_ils": 750,
    },
    {
        "rule_id": "IL-STATIC-006",
        "title_he": "חניה מעל הזמן המותר (שלט הגבלת זמן)",
        "title_en": "Parking beyond the posted time limit",
        "legal_basis_he": "תקנה 72ב — אסור לחנות מעבר לזמן המצוין בשלט הגבלת זמן",
        "legal_basis_en": "Traffic Regulations §72b — prohibited to park beyond the time indicated on the time-limit sign",
        "description_he": "שלטי הגבלת זמן (לדוגמה: '1 שעה') אוסרים חניה ממושכת. לא ניתן לאמת משך חניה מוידאו — נדרשת בדיקה ידנית.",
        "description_en": "Time-limit signs (e.g. '1 hour') prohibit extended parking. Actual duration cannot be determined from video — manual inspection of arrival time required.",
        "fine_ils": 250,
    },
    {
        "rule_id": "IL-STATIC-007",
        "title_he": "חניה ללא תג דיירים באזור חניה לדיירים",
        "title_en": "Parking without a residents permit in a residents-only zone",
        "legal_basis_he": "תקנות החניה לדיירים — רק בעלי תג דיירים תקף מורשים לחנות באזורי דיירים",
        "legal_basis_en": "Residents Parking Regulations — only holders of a valid residents permit may park in designated zones",
        "description_he": "אזור חניה מוגבל לדיירים עם תג תקף. לא ניתן לאמת תג חניה מוידאו — נדרשת בדיקה ידנית.",
        "description_en": "Residents-only parking zone. Permit verification is not possible from video — manual inspection required.",
        "fine_ils": 250,
    },
    {
        "rule_id": "IL-STATIC-008",
        "title_he": "חניה בשעות האסורות (חניה חופשית בשעות מוגבלות)",
        "title_en": "Parking during prohibited hours (free parking with hour restrictions)",
        "legal_basis_he": "תקנה 72ד — שלטי הגבלת שעות אוסרים חניה בשעות מוגדרות (לדוגמה: ימי א'–ו' 08:00–20:00)",
        "legal_basis_en": "Traffic Regulations §72d — hour-restriction signs prohibit parking during defined periods (e.g. Sun–Fri 08:00–20:00)",
        "description_he": "שלטי הגבלת שעות מתירים חניה רק בשעות מסוימות. לא ניתן לאמת שעת החניה מוידאו בלבד — נדרשת בדיקת חותמת הזמן.",
        "description_en": "Hour-restriction signs permit free parking only outside defined hours. Parking time cannot be confirmed from video alone — timestamp verification required.",
        "fine_ils": 250,
    },
    {
        "rule_id": "IL-STATIC-013",
        "title_he": "חניה בקרבת מעבר חצייה באופן אסור",
        "title_en": "Parking too close to a pedestrian crosswalk",
        "legal_basis_he": "תקנה 71(א)(2) — אסור לחנות במרחק של פחות מ-12 מטר לפני מעבר חציה",
        "legal_basis_en": "Traffic Regulations §71(a)(2) — prohibited to park within 12 m before a crosswalk",
        "description_he": "חניית רכב בתוך 12 מטר לפני מעבר חציה חוסמת שדה ראייה של הולכי רגל ומסכנת חיים.",
        "description_en": "Parking within 12 m before a pedestrian crossing obstructs pedestrian sightlines and endangers lives.",
        "fine_ils": 500,
    },
    {
        "rule_id": "IL-STATIC-014",
        "title_he": "עצירה באזור שלט 'אסור לעצור'",
        "title_en": "Stopping where a no-stopping sign is in effect",
        "legal_basis_he": "תקנה 36(1) — שלט עגול אדום עם שתי קווים אלכסוניים מקבילים אוסר עצירה",
        "legal_basis_en": "Traffic Regulations §36(1) — red circular sign with two diagonal bars prohibits any stop",
        "description_he": "שלט עגול אדום עם שני פסים אלכסוניים מקבילים (אסור לעצור). כל עצירה אסורה.",
        "description_en": "Red circular sign with two parallel diagonal lines (no stopping). Any stop is a violation.",
        "fine_ils": 1000,
    },
    {
        "rule_id": "IL-STATIC-015",
        "title_he": "חניה באזור שלט 'אסור לחנות'",
        "title_en": "Parking where a no-parking sign is in effect",
        "legal_basis_he": "תקנה 36(2) — שלט עגול אדום עם קו אלכסוני אחד אוסר חניה (עצירה קצרה מותרת)",
        "legal_basis_en": "Traffic Regulations §36(2) — red circular sign with one diagonal bar prohibits parking",
        "description_he": "שלט עגול אדום עם פס אלכסוני אחד (אסור לחנות). מותר לעצור לעלייה/ירידה, אך חניה אסורה.",
        "description_en": "Red circular sign with one diagonal bar (no parking). Brief stops allowed, but leaving the vehicle is prohibited.",
        "fine_ils": 750,
    },
]


def seed():
    db = SessionLocal()
    try:
        added = 0
        updated = 0
        for r in RULES:
            existing = db.query(ViolationRule).filter(ViolationRule.rule_id == r["rule_id"]).first()
            if existing:
                for k, v in r.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(ViolationRule(**r))
                added += 1
        db.commit()
        print(f"Done: {added} added, {updated} updated.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
