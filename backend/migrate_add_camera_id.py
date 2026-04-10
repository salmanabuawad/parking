"""Add camera_id column to upload_jobs table (for existing databases)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine

db_url = str(engine.url)


def migrate():
    with engine.connect() as conn:
        if "sqlite" in db_url.lower():
            # SQLite: check if column exists first
            result = conn.execute(text("PRAGMA table_info(upload_jobs)"))
            columns = [row[1] for row in result]
            if "camera_id" not in columns:
                conn.execute(text("ALTER TABLE upload_jobs ADD COLUMN camera_id VARCHAR(50)"))
                conn.commit()
                print("Added camera_id column to upload_jobs (SQLite)")
            else:
                print("camera_id column already exists (SQLite)")
        else:
            # PostgreSQL
            conn.execute(text("""
                ALTER TABLE upload_jobs
                ADD COLUMN IF NOT EXISTS camera_id VARCHAR(50)
            """))
            conn.commit()
            print("Added camera_id column to upload_jobs (PostgreSQL)")


if __name__ == "__main__":
    migrate()
