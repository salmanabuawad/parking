"""Add upload_job_id column to tickets (links N tickets — one per car — to one source job/video)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine

db_url = str(engine.url)


def migrate():
    with engine.connect() as conn:
        if "sqlite" in db_url.lower():
            result = conn.execute(text("PRAGMA table_info(tickets)"))
            columns = [row[1] for row in result]
            if "upload_job_id" not in columns:
                conn.execute(text("ALTER TABLE tickets ADD COLUMN upload_job_id INTEGER"))
                conn.commit()
                print("Added upload_job_id column to tickets (SQLite)")
            else:
                print("upload_job_id column already exists (SQLite)")
        else:
            conn.execute(text("""
                ALTER TABLE tickets
                ADD COLUMN IF NOT EXISTS upload_job_id INTEGER
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_tickets_upload_job_id ON tickets (upload_job_id)
            """))
            conn.commit()
            print("Added upload_job_id column + index to tickets (PostgreSQL)")


if __name__ == "__main__":
    migrate()
