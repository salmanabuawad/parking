"""Camera grid zone-map: paint image cells with a violation type.

Revision ID: 20260703_0013
Revises: 20260702_0012
Create Date: 2026-07-03
"""
from alembic import op

revision = "20260703_0013"
down_revision = "20260702_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS zone_grid JSON")


def downgrade():
    op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS zone_grid")
