"""Add original_video_path to tickets table.

Revision ID: 20260410_0007
Revises: 20260327_0006
Create Date: 2026-04-10
"""
from alembic import op
from sqlalchemy import text

revision = "20260410_0007"
down_revision = "20260327_0006"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
        ALTER TABLE tickets
        ADD COLUMN IF NOT EXISTS original_video_path VARCHAR(500)
    """))


def downgrade():
    op.get_bind().execute(text("""
        ALTER TABLE tickets
        DROP COLUMN IF EXISTS original_video_path
    """))
