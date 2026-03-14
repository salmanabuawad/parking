"""Add missing ticket_screenshots columns for dual-schema support.

Ensures both Alembic (image_path, frame_timestamp_ms, ...) and simple
(storage_path, frame_time_sec, ...) columns exist so save works either way.
"""
from alembic import op
from sqlalchemy import text

revision = "20260314_0003"
down_revision = "20260314_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Simple schema columns (if table was created by Alembic)
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS storage_path VARCHAR(500)"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS frame_time_sec FLOAT"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS captured_at TIMESTAMP WITH TIME ZONE"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS created_by VARCHAR(50)"))
    # Alembic columns (if table was created by simple migration)
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS image_path VARCHAR(500)"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS frame_timestamp_ms BIGINT"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS video_timestamp_text VARCHAR(64)"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS captured_by VARCHAR(100)"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS thumbnail_path VARCHAR(500)"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS source_video_hash VARCHAR(128)"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS capture_note TEXT"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS frame_width INTEGER"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS frame_height INTEGER"))
    conn.execute(text("ALTER TABLE ticket_screenshots ADD COLUMN IF NOT EXISTS is_blurred_source BOOLEAN DEFAULT true"))


def downgrade() -> None:
    pass  # Leave columns in place; no safe way to drop without knowing which were added
