"""app_config blur_expand_ratio, temporal_blur columns

Revision ID: 20260314_0002
Revises: 20260314_0001
Create Date: 2026-03-14

"""
from alembic import op
from sqlalchemy import text

revision = "20260314_0002"
down_revision = "20260314_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add temporal blur and expand ratio columns to app_config (idempotent for Postgres)."""
    conn = op.get_bind()
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS blur_expand_ratio FLOAT DEFAULT 0.25
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS temporal_blur_enabled BOOLEAN DEFAULT TRUE
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS temporal_blur_max_misses INTEGER DEFAULT 3
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS blur_expand_ratio"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS temporal_blur_enabled"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS temporal_blur_max_misses"))
