"""ANPR per-track results table for dashboard.

Revision ID: 20260410_0008
Revises: 20260410_0007
Create Date: 2026-04-10
"""
from alembic import op
from sqlalchemy import text

revision = "20260410_0008"
down_revision = "20260410_0007"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS anpr_track_results (
            id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
            track_id INTEGER NOT NULL,
            raw_digits VARCHAR(16) NOT NULL,
            normalized_plate VARCHAR(32) NOT NULL,
            vote_count INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_anpr_track_results_ticket_id ON anpr_track_results (ticket_id)"))


def downgrade():
    op.get_bind().execute(text("DROP TABLE IF EXISTS anpr_track_results"))
