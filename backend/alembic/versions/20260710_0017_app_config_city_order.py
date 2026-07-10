"""App config: city display order for the fleet dashboard / camera city dropdowns.

Revision ID: 20260710_0017
Revises: 20260703_0016
Create Date: 2026-07-10
"""
from alembic import op

revision = "20260710_0017"
down_revision = "20260703_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS city_order JSON")


def downgrade():
    op.execute("ALTER TABLE app_config DROP COLUMN IF EXISTS city_order")
