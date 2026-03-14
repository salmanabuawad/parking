"""Add processing_started_at to upload_jobs table for stuck-job reset threshold."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine


def migrate():
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'upload_jobs' AND column_name = 'processing_started_at'
        """))
        if r.fetchone():
            print("processing_started_at already exists. Skipping.")
            conn.commit()
            return
        conn.execute(text(
            "ALTER TABLE upload_jobs ADD COLUMN processing_started_at TIMESTAMP WITH TIME ZONE"
        ))
        conn.commit()
        print("Added processing_started_at to upload_jobs")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
