"""Add parking_zones table and camera_zones junction.

Revision ID: 20260315_0005
Revises: 20260315_0004
Create Date: 2026-03-15
"""
from alembic import op
from sqlalchemy import text

revision = "20260315_0005"
down_revision = "20260315_0004"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS parking_zones (
            id SERIAL PRIMARY KEY,
            zone_code VARCHAR(40) UNIQUE NOT NULL,
            name_he VARCHAR(100) NOT NULL,
            name_en VARCHAR(100) NOT NULL,
            description_he TEXT,
            description_en TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS camera_zones (
            camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
            zone_id INTEGER NOT NULL REFERENCES parking_zones(id) ON DELETE CASCADE,
            PRIMARY KEY (camera_id, zone_id)
        )
    """))

    # Seed the standard Israeli parking zone types
    zones = [
        ("red_white",     "אדום-לבן",          "Red-White (No Parking)",          "איסור חניה מוחלט",                          "Absolute no-parking zone (red-white curb)"),
        ("blue_white",    "כחול-לבן",           "Blue-White (Paid Parking)",        "חניה בתשלום",                               "Paid parking zone (blue-white curb)"),
        ("residents_only","תושבים בלבד",         "Residents Only",                   "חניה לתושבי השכונה בלבד",                   "Parking for local residents only"),
        ("time_limited",  "הגבלת זמן",          "Time-Limited Parking",             "חניה מוגבלת בזמן",                          "Parking allowed up to a maximum time"),
        ("free_hours",    "חינם בשעות מסוימות", "Free Parking (Certain Hours)",     "חניה חינם בשעות ספציפיות",                  "Parking free during specific hours"),
        ("no_stopping",   "אסור עצירה",         "No Stopping Zone",                 "איסור עצירה",                               "No stopping at any time"),
        ("loading_only",  "פריקה וטעינה",       "Loading/Unloading Only",           "אזור פריקה וטעינה בלבד",                    "Loading and unloading zone only"),
        ("disabled",      "נכים",               "Disabled Parking",                 "חניה לנכים",                                "Reserved for disabled permit holders"),
    ]
    for code, name_he, name_en, desc_he, desc_en in zones:
        conn.execute(text("""
            INSERT INTO parking_zones (zone_code, name_he, name_en, description_he, description_en, is_active)
            VALUES (:code, :nhe, :nen, :dhe, :den, TRUE)
            ON CONFLICT (zone_code) DO NOTHING
        """), {"code": code, "nhe": name_he, "nen": name_en, "dhe": desc_he, "den": desc_en})


def downgrade():
    op.get_bind().execute(text("DROP TABLE IF EXISTS camera_zones"))
    op.get_bind().execute(text("DROP TABLE IF EXISTS parking_zones"))
