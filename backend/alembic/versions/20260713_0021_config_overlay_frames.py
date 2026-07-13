"""System config (#1/#6): video-length bounds, timestamp overlay position, plate-inset toggle,
pending/approved subject-frame colors.

Revision ID: 20260713_0021
Revises: 20260713_0020
Create Date: 2026-07-13
"""
from alembic import op

revision = "20260713_0021"
down_revision = "20260713_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS min_video_seconds INTEGER NOT NULL DEFAULT 3")
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS max_video_seconds INTEGER NOT NULL DEFAULT 120")
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS timestamp_overlay_position VARCHAR(20) NOT NULL DEFAULT 'top_right'")
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS plate_inset_enabled BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS pending_frame_color VARCHAR(20) NOT NULL DEFAULT '#00FF00'")
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS approved_frame_color VARCHAR(20) NOT NULL DEFAULT '#FF0000'")


def downgrade():
    for col in ("min_video_seconds", "max_video_seconds", "timestamp_overlay_position",
                "plate_inset_enabled", "pending_frame_color", "approved_frame_color"):
        op.execute(f"ALTER TABLE app_config DROP COLUMN IF EXISTS {col}")
