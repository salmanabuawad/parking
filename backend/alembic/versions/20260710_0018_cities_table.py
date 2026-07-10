"""Admin-managed cities table (replaces the hardcoded CITIES dict).

Revision ID: 20260710_0018
Revises: 20260710_0017
Create Date: 2026-07-10
"""
from alembic import op

revision = "20260710_0018"
down_revision = "20260710_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cities (
            id           SERIAL PRIMARY KEY,
            key          VARCHAR(60)  NOT NULL UNIQUE,
            label        VARCHAR(120) NOT NULL,
            center_lat   DOUBLE PRECISION NOT NULL,
            center_lng   DOUBLE PRECISION NOT NULL,
            zoom         DOUBLE PRECISION NOT NULL DEFAULT 13,
            bounds       JSON,
            sort_order   INTEGER NOT NULL DEFAULT 0,
            is_active    BOOLEAN NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ DEFAULT now(),
            updated_at   TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_cities_key ON cities (key)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS cities")
