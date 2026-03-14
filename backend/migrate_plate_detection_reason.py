"""Add plate_detection_reason to tickets table if missing."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine


def migrate():
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tickets' AND column_name = 'plate_detection_reason'
        """))
        if r.fetchone():
            print("plate_detection_reason already exists. Skipping.")
            conn.commit()
            return
        conn.execute(text(
            "ALTER TABLE tickets ADD COLUMN plate_detection_reason TEXT"
        ))
        conn.commit()
        print("Added plate_detection_reason")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
