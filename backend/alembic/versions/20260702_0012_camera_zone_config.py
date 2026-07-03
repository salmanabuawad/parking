"""Camera zone-configuration: snapshot + calibration fields for drawing enforcement sections.

Revision ID: 20260702_0012
Revises: 20260701_0011
Create Date: 2026-07-02
"""
from alembic import op

revision = "20260702_0012"
down_revision = "20260701_0011"
branch_labels = None
depends_on = None

_COLS = [
    ("source_type", "VARCHAR(20)"),
    ("rtsp_url", "VARCHAR(500)"),
    ("snapshot_path", "VARCHAR(255)"),
    ("calibration_width", "INTEGER"),
    ("calibration_height", "INTEGER"),
]


def upgrade():
    for name, ddl in _COLS:
        op.execute(f"ALTER TABLE cameras ADD COLUMN IF NOT EXISTS {name} {ddl}")


def downgrade():
    for name, _ddl in _COLS:
        op.execute(f"ALTER TABLE cameras DROP COLUMN IF EXISTS {name}")
