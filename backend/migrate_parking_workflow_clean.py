"""Workflow cleanup migration for parking ticket workflow requirements.

Run:
    cd backend
    python migrate_parking_workflow_clean.py

This script is idempotent and safe to re-run. It ensures the database has:
- App/system configuration timing and retention fields.
- Camera assigned inspector + calibration fields.
- Camera segments table.
- Inspector table.
- Ticket workflow/review fields.
- Audit log and vehicle exemptions tables.
- Violation-rule evidence/timing fields.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401  # ensure all models are registered


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(engine).get_table_names()


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {c["name"] for c in inspect(engine).get_columns(table_name)}


def _exec(sql: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql))


def _add_column(table: str, column: str, ddl: str) -> None:
    if table not in inspect(engine).get_table_names():
        return
    if column in _columns(table):
        return
    print(f"Adding {table}.{column}")
    _exec(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _ensure_columns() -> None:
    # System config / retention / timing
    _add_column("app_config", "violation_dwell_seconds", "INTEGER NOT NULL DEFAULT 300")
    _add_column("app_config", "required_video_seconds", "INTEGER NOT NULL DEFAULT 10")
    _add_column("app_config", "evidence_video_pre_seconds", "INTEGER NOT NULL DEFAULT 5")
    _add_column("app_config", "evidence_video_post_seconds", "INTEGER NOT NULL DEFAULT 5")
    _add_column("app_config", "video_retention_days", "INTEGER NOT NULL DEFAULT 90")
    _add_column("app_config", "original_video_retention_days", "INTEGER NOT NULL DEFAULT 180")
    _add_column("app_config", "processed_video_retention_days", "INTEGER NOT NULL DEFAULT 90")
    _add_column("app_config", "ticket_candidate_retention_days", "INTEGER NOT NULL DEFAULT 365")
    _add_column("app_config", "video_timestamp_overlay", "BOOLEAN NOT NULL DEFAULT TRUE")

    # Camera assignment/calibration
    _add_column("cameras", "assigned_inspector_id", "INTEGER NULL")
    _add_column("cameras", "range_config", "JSON NULL")
    _add_column("cameras", "source_type", "VARCHAR(20) NULL DEFAULT 'uploaded_image'")
    _add_column("cameras", "rtsp_url", "VARCHAR(500) NULL")
    _add_column("cameras", "snapshot_path", "VARCHAR(255) NULL")
    _add_column("cameras", "calibration_width", "INTEGER NULL")
    _add_column("cameras", "calibration_height", "INTEGER NULL")
    _add_column("cameras", "zone_grid", "JSON NULL")
    # Enforcement schedule — per-day working hours (+ legacy flat fields)
    _add_column("cameras", "active_schedule", "JSON NULL")
    _add_column("cameras", "active_days", "JSON NULL")
    _add_column("cameras", "active_from_time", "VARCHAR(10) NULL")
    _add_column("cameras", "active_to_time", "VARCHAR(10) NULL")

    # Violation types/rules timing + required evidence
    _add_column("violation_rules", "default_min_stay_seconds", "INTEGER NOT NULL DEFAULT 30")
    _add_column("violation_rules", "default_evidence_video_seconds", "INTEGER NOT NULL DEFAULT 20")
    _add_column("violation_rules", "requires_start_image", "BOOLEAN NOT NULL DEFAULT TRUE")
    _add_column("violation_rules", "requires_end_image", "BOOLEAN NOT NULL DEFAULT TRUE")
    _add_column("violation_rules", "requires_clear_plate_image", "BOOLEAN NOT NULL DEFAULT TRUE")
    _add_column("violation_rules", "requires_context_image", "BOOLEAN NOT NULL DEFAULT TRUE")
    _add_column("violation_rules", "requires_continuous_video", "BOOLEAN NOT NULL DEFAULT TRUE")

    # Ticket workflow
    _add_column("tickets", "violation_start_at", "TIMESTAMP NULL")
    _add_column("tickets", "violation_end_at", "TIMESTAMP NULL")
    _add_column("tickets", "violation_duration_seconds", "FLOAT NULL")
    _add_column("tickets", "assigned_inspector_id", "INTEGER NULL")
    _add_column("tickets", "approved_by_inspector_id", "INTEGER NULL")
    _add_column("tickets", "inspector_approved_at", "TIMESTAMP NULL")
    _add_column("tickets", "inspector_reviewed_at", "TIMESTAMP NULL")
    _add_column("tickets", "inspector_decision", "VARCHAR(30) NULL")
    _add_column("tickets", "review_status", "VARCHAR(40) NULL")
    _add_column("tickets", "inspector_violation_rule_id", "VARCHAR(30) NULL")
    _add_column("tickets", "inspector_plate", "VARCHAR(20) NULL")
    _add_column("tickets", "inspector_vehicle_color", "VARCHAR(100) NULL")
    _add_column("tickets", "inspector_vehicle_type", "VARCHAR(100) NULL")
    _add_column("tickets", "inspector_vehicle_make", "VARCHAR(100) NULL")
    _add_column("tickets", "inspector_vehicle_model", "VARCHAR(100) NULL")
    _add_column("tickets", "camera_section_id", "INTEGER NULL")
    _add_column("tickets", "vehicle_registry_lookup_status", "VARCHAR(40) NULL")
    _add_column("tickets", "vehicle_registry_raw_json", "JSON NULL")
    _add_column("tickets", "vehicle_registry_checked_at", "TIMESTAMP NULL")
    _add_column("tickets", "start_violation_screenshot_id", "INTEGER NULL")
    _add_column("tickets", "end_violation_screenshot_id", "INTEGER NULL")
    _add_column("tickets", "clear_plate_screenshot_id", "INTEGER NULL")
    _add_column("tickets", "violation_context_screenshot_id", "INTEGER NULL")
    _add_column("tickets", "suspected_vehicle_box", "JSON NULL")
    _add_column("tickets", "suspected_vehicle_track_id", "VARCHAR(40) NULL")
    _add_column("tickets", "suspected_vehicle_marker_state", "VARCHAR(20) NOT NULL DEFAULT 'pending'")
    _add_column("tickets", "camera_config_snapshot", "JSON NULL")
    _add_column("tickets", "camera_section_snapshot", "JSON NULL")
    _add_column("tickets", "violation_rule_snapshot", "JSON NULL")
    _add_column("tickets", "system_config_snapshot", "JSON NULL")
    _add_column("tickets", "original_video_sha256", "VARCHAR(64) NULL")
    _add_column("tickets", "evidence_video_sha256", "VARCHAR(64) NULL")
    _add_column("tickets", "best_frame_sha256", "VARCHAR(64) NULL")
    _add_column("tickets", "plate_crop_sha256", "VARCHAR(64) NULL")

    # Screenshots role
    _add_column("ticket_screenshots", "role", "VARCHAR(40) NULL")


def _seed_defaults() -> None:
    db = SessionLocal()
    try:
        from app.models import AppConfig, ViolationRule

        if not db.query(AppConfig).first():
            db.add(AppConfig(id=1))

        two_wheels = db.query(ViolationRule).filter(ViolationRule.rule_id == "IL-STATIC-016").first()
        if not two_wheels:
            db.add(ViolationRule(
                rule_id="IL-STATIC-016",
                title_he="שני גלגלים על המדרכה",
                title_en="Two wheels on sidewalk",
                description_he="הרכב חונה כך ששני גלגלים נמצאים על המדרכה או באזור הולכי רגל.",
                description_en="Vehicle parked with two wheels on the sidewalk or pedestrian area.",
                legal_basis_he="לפי הוראות התמרור/חוק העזר המקומי.",
                legal_basis_en="According to signage/municipal bylaw.",
                fine_ils=500,
                default_min_stay_seconds=30,
                default_evidence_video_seconds=20,
            ))
        db.commit()
    finally:
        db.close()


def main() -> None:
    _ensure_tables()
    _ensure_columns()
    _seed_defaults()
    print("Workflow cleanup migration completed.")


if __name__ == "__main__":
    main()
