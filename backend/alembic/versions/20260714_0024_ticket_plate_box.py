"""Plate bounding box on tickets (#10): tickets.plate_box.

Companion to the existing suspected_vehicle_box (car bbox). Both are JSON [x1,y1,x2,y2]
in video pixels, surfaced by the multi-car ANPR pipeline so the review UI can draw the
suspected vehicle and its plate.

Revision ID: 20260714_0024
Revises: 20260714_0023
Create Date: 2026-07-14
"""
from alembic import op

revision = "20260714_0024"
down_revision = "20260714_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS plate_box JSONB")


def downgrade():
    op.execute("ALTER TABLE tickets DROP COLUMN IF EXISTS plate_box")
