"""Camera city grouping for the multi-city fleet dashboard.

Revision ID: 20260703_0016
Revises: 20260703_0015
Create Date: 2026-07-03
"""
from alembic import op

revision = "20260703_0016"
down_revision = "20260703_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS city VARCHAR(30)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cameras_city ON cameras (city)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_cameras_city")
    op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS city")
