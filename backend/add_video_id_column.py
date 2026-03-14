"""Add video_id column to tickets if missing."""
from app.database import engine

with engine.connect() as conn:
    conn.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS video_id INTEGER")
    conn.commit()
    print("Done.")
