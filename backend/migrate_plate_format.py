"""Add plate_format to tickets table if missing (ref: plate format classification)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine


def migrate():
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tickets' AND column_name = 'plate_format'
        """))
        if r.fetchone():
            print("plate_format already exists. Skipping.")
            conn.commit()
            return
        conn.execute(text(
            "ALTER TABLE tickets ADD COLUMN plate_format VARCHAR(50)"
        ))
        conn.commit()
        print("Added plate_format")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
