"""App config: blur_except_plate — keep only the enforced plate sharp, blur the rest of the frame.

Revision ID: 20260713_0019
Revises: 20260710_0018
Create Date: 2026-07-13
"""
from alembic import op

revision = "20260713_0019"
down_revision = "20260710_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS blur_except_plate BOOLEAN NOT NULL DEFAULT TRUE")


def downgrade():
    op.execute("ALTER TABLE app_config DROP COLUMN IF EXISTS blur_except_plate")
