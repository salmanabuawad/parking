"""Initial schema: create all base tables.

Revision ID: 20260314_0000
Revises:
Create Date: 2026-03-14 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260314_0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("connection_type", sa.String(length=20), nullable=False, server_default="ip"),
        sa.Column("connection_config", sa.JSON(), nullable=True),
        sa.Column("param_source", sa.String(length=25), nullable=True, server_default="manual"),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("manufacturer", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cameras_id", "cameras", ["id"])

    op.create_table(
        "camera_videos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=True, server_default="video/mp4"),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_camera_videos_id", "camera_videos", ["id"])

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_admins_id", "admins", ["id"])
    op.create_index("ix_admins_username", "admins", ["username"], unique=True)

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("license_plate", sa.String(length=20), nullable=False),
        sa.Column("plate_detection_reason", sa.Text(), nullable=True),
        sa.Column("plate_format", sa.String(length=50), nullable=True),
        sa.Column("camera_id", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("violation_zone", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("fine_amount", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="pending_review"),
        sa.Column("video_path", sa.String(length=500), nullable=True),
        sa.Column("ticket_image_path", sa.String(length=500), nullable=True),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("processed_video_id", sa.Integer(), nullable=True),
        sa.Column("ticket_image_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_params", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upload_job_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_tickets_id", "tickets", ["id"])

    op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("blur_kernel_size", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("use_violation_pipeline", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_app_config_id", "app_config", ["id"])

    op.create_table(
        "upload_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("raw_video_id", sa.Integer(), nullable=True),
        sa.Column("raw_video_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="queued"),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticket_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_plate", sa.String(length=20), nullable=True, server_default=""),
        sa.Column("violation_zone", sa.String(length=20), nullable=True, server_default="red_white"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("submitted_by", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_upload_jobs_id", "upload_jobs", ["id"])


def downgrade() -> None:
    op.drop_table("upload_jobs")
    op.drop_table("app_config")
    op.drop_table("tickets")
    op.drop_table("admins")
    op.drop_table("camera_videos")
    op.drop_table("cameras")
