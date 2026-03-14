"""Add raw_video_path to upload_jobs, make raw_video_id nullable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine

db_url = str(engine.url)


def migrate_postgres():
    with engine.connect() as conn:
        # Check if raw_video_path exists
        r = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'upload_jobs' AND column_name = 'raw_video_path'
        """))
        if not r.fetchone():
            conn.execute(text("ALTER TABLE upload_jobs ADD COLUMN raw_video_path VARCHAR(500)"))
            print("Added raw_video_path")
        conn.execute(text("ALTER TABLE upload_jobs ALTER COLUMN raw_video_id DROP NOT NULL"))
        conn.commit()
    print("Migration complete (PostgreSQL)")


def migrate_sqlite():
    # SQLite: add column, recreate table for NOT NULL change - skip for simplicity
    with engine.connect() as conn:
        r = conn.execute(text("PRAGMA table_info(upload_jobs)"))
        cols = [row[1] for row in r.fetchall()]
        if "raw_video_path" not in cols:
            conn.execute(text("ALTER TABLE upload_jobs ADD COLUMN raw_video_path VARCHAR(500)"))
            print("Added raw_video_path")
        conn.commit()
    print("Migration complete (SQLite)")


if __name__ == "__main__":
    if "sqlite" in db_url.lower():
        migrate_sqlite()
    else:
        migrate_postgres()
