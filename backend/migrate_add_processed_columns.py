"""Add processed_video_id and ticket_image_id to tickets table."""
import os
import sys

# Add parent so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine


def migrate():
    with engine.connect() as conn:
        for col in ("processed_video_id", "ticket_image_id"):
            r = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tickets' AND column_name = :col
            """), {"col": col})
            if r.fetchone():
                print(f"{col} already exists. Skipping.")
                continue
            conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {col} INTEGER"))
            print(f"Added {col}")
        conn.commit()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
