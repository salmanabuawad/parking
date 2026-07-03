"""Camera geographic placement (latitude/longitude) for the cameras map view.

Revision ID: 20260703_0014
Revises: 20260703_0013
Create Date: 2026-07-03
"""
from alembic import op

revision = "20260703_0014"
down_revision = "20260703_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION")
    op.execute("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION")


def downgrade():
    op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS longitude")
    op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS latitude")
