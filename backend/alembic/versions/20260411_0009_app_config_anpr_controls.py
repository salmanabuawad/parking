"""Add ANPR controls to app_config.

Revision ID: 20260411_0009
Revises: 20260410_0008
Create Date: 2026-04-11
"""
from alembic import op
from sqlalchemy import text

revision = "20260411_0009"
down_revision = "20260410_0008"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS anpr_detector_backend VARCHAR(20) DEFAULT 'enterprise'
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS anpr_ocr_every_n_frames INTEGER DEFAULT 2
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS enterprise_detection_zoom FLOAT DEFAULT 1.75
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS enterprise_detection_roi_y_start FLOAT DEFAULT 0.26
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE app_config
            SET anpr_detector_backend = COALESCE(anpr_detector_backend, 'enterprise'),
                anpr_ocr_every_n_frames = COALESCE(anpr_ocr_every_n_frames, 2),
                enterprise_detection_zoom = COALESCE(enterprise_detection_zoom, 1.75),
                enterprise_detection_roi_y_start = COALESCE(enterprise_detection_roi_y_start, 0.26)
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS enterprise_detection_roi_y_start"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS enterprise_detection_zoom"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS anpr_ocr_every_n_frames"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS anpr_detector_backend"))
