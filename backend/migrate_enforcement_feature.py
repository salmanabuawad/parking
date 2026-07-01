"""Schema for the enforcement feature (idempotent).

Adds:
  * inspectors table (field officers who log in & approve)
  * camera_segments table (labeled segment + its own violation types, per camera)
  * app_config system settings: dwell seconds, required clip length, retention, video-clock toggle
  * tickets: violation_start_at/end_at + inspector-approval fields

Run from the backend dir (venv + .env): python migrate_enforcement_feature.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine

IS_SQLITE = "sqlite" in str(engine.url).lower()
TS = "TIMESTAMP" if IS_SQLITE else "TIMESTAMPTZ"

APP_CONFIG_COLS = [
    ("violation_dwell_seconds", "INTEGER NOT NULL DEFAULT 300"),
    ("required_video_seconds", "INTEGER NOT NULL DEFAULT 10"),
    ("video_retention_days", "INTEGER NOT NULL DEFAULT 90"),
    ("video_timestamp_overlay", "BOOLEAN NOT NULL DEFAULT TRUE"),
]
TICKET_COLS = [
    ("violation_start_at", TS),
    ("violation_end_at", TS),
    ("approved_by_inspector_id", "INTEGER"),
    ("assigned_inspector_id", "INTEGER"),
    ("inspector_approved_at", TS),
    ("inspector_violation_rule_id", "VARCHAR(30)"),
    ("inspector_plate", "VARCHAR(20)"),
]
CAMERA_COLS = [
    ("assigned_inspector_id", "INTEGER"),
]
SCREENSHOT_COLS = [
    ("role", "VARCHAR(40)"),
]

_PK = "INTEGER PRIMARY KEY AUTOINCREMENT" if IS_SQLITE else "SERIAL PRIMARY KEY"
_NOW = "CURRENT_TIMESTAMP" if IS_SQLITE else "now()"

INSPECTORS_DDL = f"""
CREATE TABLE IF NOT EXISTS inspectors (
    id {_PK},
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    badge_number VARCHAR(40),
    phone VARCHAR(40),
    email VARCHAR(120),
    role VARCHAR(20) NOT NULL DEFAULT 'inspector',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at {TS} DEFAULT {_NOW},
    updated_at {TS}
)
"""

SEGMENTS_DDL = f"""
CREATE TABLE IF NOT EXISTS camera_segments (
    id {_PK},
    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    label VARCHAR(200) NOT NULL,
    violation_rule_ids JSON,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at {TS} DEFAULT {_NOW},
    updated_at {TS}
)
"""


def _add_columns(conn, table, cols):
    if IS_SQLITE:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        for name, ddl in cols:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    else:
        for name, ddl in cols:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}"))


def migrate():
    with engine.begin() as conn:
        conn.execute(text(INSPECTORS_DDL))
        conn.execute(text(SEGMENTS_DDL))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_camera_segments_camera_id ON camera_segments (camera_id)"))
        _add_columns(conn, "app_config", APP_CONFIG_COLS)
        _add_columns(conn, "tickets", TICKET_COLS)
        _add_columns(conn, "cameras", CAMERA_COLS)
        _add_columns(conn, "ticket_screenshots", SCREENSHOT_COLS)
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_approved_by_inspector_id ON tickets (approved_by_inspector_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_assigned_inspector_id ON tickets (assigned_inspector_id)"))
    print("Enforcement-feature migration applied (inspectors, camera_segments, app_config, tickets).")


if __name__ == "__main__":
    migrate()
