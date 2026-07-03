"""Camera operational status for the fleet dashboard.

Revision ID: 20260703_0015
Revises: 20260703_0014
Create Date: 2026-07-03
"""
from alembic import op

revision = "20260703_0015"
down_revision = "20260703_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'online'")


def downgrade():
    op.execute("ALTER TABLE cameras DROP COLUMN IF EXISTS status")
