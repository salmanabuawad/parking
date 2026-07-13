"""Violation-type semantic code (#2): violation_rules.violation_code.

Revision ID: 20260713_0022
Revises: 20260713_0021
Create Date: 2026-07-13
"""
from alembic import op

revision = "20260713_0022"
down_revision = "20260713_0021"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE violation_rules ADD COLUMN IF NOT EXISTS violation_code VARCHAR(40)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_violation_rules_violation_code ON violation_rules (violation_code)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_violation_rules_violation_code")
    op.execute("ALTER TABLE violation_rules DROP COLUMN IF EXISTS violation_code")
