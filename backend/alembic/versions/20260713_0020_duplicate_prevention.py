"""Duplicate-prevention fields (#14): AppConfig.duplicate_ticket_window_seconds + tickets.duplicate_of_ticket_id.

Revision ID: 20260713_0020
Revises: 20260713_0019
Create Date: 2026-07-13
"""
from alembic import op

revision = "20260713_0020"
down_revision = "20260713_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE app_config ADD COLUMN IF NOT EXISTS duplicate_ticket_window_seconds INTEGER NOT NULL DEFAULT 300")
    op.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS duplicate_of_ticket_id INTEGER")


def downgrade():
    op.execute("ALTER TABLE tickets DROP COLUMN IF EXISTS duplicate_of_ticket_id")
    op.execute("ALTER TABLE app_config DROP COLUMN IF EXISTS duplicate_ticket_window_seconds")
