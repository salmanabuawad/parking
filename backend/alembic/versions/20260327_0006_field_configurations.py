"""Add field_configurations table.

Revision ID: 20260327_0006
Revises: 20260315_0005
Create Date: 2026-03-27
"""
from alembic import op
from sqlalchemy import text

revision = "20260327_0006"
down_revision = "20260315_0005"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS field_configurations (
            id SERIAL PRIMARY KEY,
            grid_name VARCHAR(100) NOT NULL,
            field_name VARCHAR(100) NOT NULL,
            width_chars INTEGER NOT NULL DEFAULT 10,
            padding INTEGER NOT NULL DEFAULT 8,
            hebrew_name VARCHAR(200),
            pinned BOOLEAN NOT NULL DEFAULT FALSE,
            pin_side VARCHAR(10),
            visible BOOLEAN NOT NULL DEFAULT TRUE,
            column_order INTEGER,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ,
            UNIQUE (grid_name, field_name)
        )
    """))


def downgrade():
    op.get_bind().execute(text("DROP TABLE IF EXISTS field_configurations"))
