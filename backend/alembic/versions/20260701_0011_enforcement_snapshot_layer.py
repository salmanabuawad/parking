"""Enforcement + inspector-review + snapshot layer.

Folds the standalone enforcement schema (inspectors, camera_segments, app_config/tickets/cameras
columns) into Alembic and adds the snippet layer: per-violation-type evidence/timing requirements,
camera-section geometry + schedule, ticket snapshots / registry-result / evidence-image / marker /
integrity-hash fields, ticket_audit_log, vehicle_exemptions.

All statements are idempotent (IF NOT EXISTS) so this applies cleanly to the existing prod DB (where
the enforcement columns already exist out-of-band) and to a fresh alembic-only database.

Revision ID: 20260701_0011
Revises: 20260411_0010
Create Date: 2026-07-01
"""
from alembic import op
from sqlalchemy import text

revision = "20260701_0011"
down_revision = "20260411_0010"
branch_labels = None
depends_on = None


INSPECTORS_DDL = """
CREATE TABLE IF NOT EXISTS inspectors (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    badge_number VARCHAR(40),
    phone VARCHAR(40),
    email VARCHAR(120),
    role VARCHAR(20) NOT NULL DEFAULT 'inspector',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
)
"""
SEGMENTS_DDL = """
CREATE TABLE IF NOT EXISTS camera_segments (
    id SERIAL PRIMARY KEY,
    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    label VARCHAR(200) NOT NULL,
    violation_rule_ids JSON,
    coordinate_type VARCHAR(20) NOT NULL DEFAULT 'pixels',
    x1 DOUBLE PRECISION, y1 DOUBLE PRECISION, x2 DOUBLE PRECISION, y2 DOUBLE PRECISION,
    polygon_json JSON,
    min_stay_seconds INTEGER,
    evidence_video_seconds INTEGER,
    active_days JSON,
    active_from_time VARCHAR(10),
    active_to_time VARCHAR(10),
    holiday_policy VARCHAR(30),
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
)
"""
AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS ticket_audit_log (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    inspector_id INTEGER REFERENCES inspectors(id),
    action_type VARCHAR(50) NOT NULL,
    old_value_json JSON,
    new_value_json JSON,
    notes TEXT,
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""
EXEMPTIONS_DDL = """
CREATE TABLE IF NOT EXISTS vehicle_exemptions (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    exemption_type VARCHAR(50) NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
)
"""

APP_CONFIG_COLS = [
    ("violation_dwell_seconds", "INTEGER NOT NULL DEFAULT 300"),
    ("required_video_seconds", "INTEGER NOT NULL DEFAULT 10"),
    ("video_retention_days", "INTEGER NOT NULL DEFAULT 90"),
    ("video_timestamp_overlay", "BOOLEAN NOT NULL DEFAULT TRUE"),
]
CAMERA_COLS = [
    ("assigned_inspector_id", "INTEGER"),
    ("range_config", "JSON"),
]
VIOLATION_RULE_COLS = [
    ("default_min_stay_seconds", "INTEGER NOT NULL DEFAULT 30"),
    ("default_evidence_video_seconds", "INTEGER NOT NULL DEFAULT 20"),
    ("requires_start_image", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("requires_end_image", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("requires_clear_plate_image", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("requires_context_image", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("requires_continuous_video", "BOOLEAN NOT NULL DEFAULT TRUE"),
]
SEGMENT_COLS = [
    ("coordinate_type", "VARCHAR(20) NOT NULL DEFAULT 'pixels'"),
    ("x1", "DOUBLE PRECISION"), ("y1", "DOUBLE PRECISION"),
    ("x2", "DOUBLE PRECISION"), ("y2", "DOUBLE PRECISION"),
    ("polygon_json", "JSON"),
    ("min_stay_seconds", "INTEGER"),
    ("evidence_video_seconds", "INTEGER"),
    ("active_days", "JSON"),
    ("active_from_time", "VARCHAR(10)"),
    ("active_to_time", "VARCHAR(10)"),
    ("holiday_policy", "VARCHAR(30)"),
]
SCREENSHOT_COLS = [("role", "VARCHAR(40)")]
TICKET_COLS = [
    # enforcement fold-in
    ("violation_start_at", "TIMESTAMPTZ"),
    ("violation_end_at", "TIMESTAMPTZ"),
    ("approved_by_inspector_id", "INTEGER"),
    ("assigned_inspector_id", "INTEGER"),
    ("inspector_approved_at", "TIMESTAMPTZ"),
    ("inspector_violation_rule_id", "VARCHAR(30)"),
    ("inspector_plate", "VARCHAR(20)"),
    # snippet layer
    ("inspector_reviewed_at", "TIMESTAMPTZ"),
    ("inspector_decision", "VARCHAR(30)"),
    ("review_status", "VARCHAR(40)"),
    ("violation_duration_seconds", "DOUBLE PRECISION"),
    ("camera_section_id", "INTEGER"),
    ("inspector_vehicle_color", "VARCHAR(100)"),
    ("inspector_vehicle_type", "VARCHAR(100)"),
    ("inspector_vehicle_make", "VARCHAR(100)"),
    ("inspector_vehicle_model", "VARCHAR(100)"),
    ("vehicle_registry_lookup_status", "VARCHAR(40)"),
    ("vehicle_registry_raw_json", "JSON"),
    ("vehicle_registry_checked_at", "TIMESTAMPTZ"),
    ("start_violation_screenshot_id", "INTEGER"),
    ("end_violation_screenshot_id", "INTEGER"),
    ("clear_plate_screenshot_id", "INTEGER"),
    ("violation_context_screenshot_id", "INTEGER"),
    ("suspected_vehicle_box", "JSON"),
    ("suspected_vehicle_track_id", "VARCHAR(40)"),
    ("suspected_vehicle_marker_state", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
    ("camera_config_snapshot", "JSON"),
    ("camera_section_snapshot", "JSON"),
    ("violation_rule_snapshot", "JSON"),
    ("system_config_snapshot", "JSON"),
    ("original_video_sha256", "VARCHAR(64)"),
    ("evidence_video_sha256", "VARCHAR(64)"),
    ("best_frame_sha256", "VARCHAR(64)"),
    ("plate_crop_sha256", "VARCHAR(64)"),
]


def _add_cols(conn, table, cols):
    for name, ddl in cols:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}"))


def upgrade():
    conn = op.get_bind()
    conn.execute(text(INSPECTORS_DDL))
    conn.execute(text(SEGMENTS_DDL))
    conn.execute(text(AUDIT_DDL))
    conn.execute(text(EXEMPTIONS_DDL))
    _add_cols(conn, "app_config", APP_CONFIG_COLS)
    _add_cols(conn, "cameras", CAMERA_COLS)
    _add_cols(conn, "violation_rules", VIOLATION_RULE_COLS)
    _add_cols(conn, "camera_segments", SEGMENT_COLS)
    _add_cols(conn, "ticket_screenshots", SCREENSHOT_COLS)
    _add_cols(conn, "tickets", TICKET_COLS)
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_camera_segments_camera_id ON camera_segments (camera_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_approved_by_inspector_id ON tickets (approved_by_inspector_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tickets_assigned_inspector_id ON tickets (assigned_inspector_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_audit_log_ticket_id ON ticket_audit_log (ticket_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_vehicle_exemptions_plate ON vehicle_exemptions (plate_number)"))


def downgrade():
    # Additive, non-destructive layer — leave columns/tables in place on downgrade.
    pass
