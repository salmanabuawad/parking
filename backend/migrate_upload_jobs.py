"""Add upload_jobs table matching UploadJob model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text
from app.database import engine

# Detect PostgreSQL vs SQLite
db_url = str(engine.url)


def migrate_postgres():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS upload_jobs (
                id SERIAL PRIMARY KEY,
                raw_video_id INTEGER NOT NULL REFERENCES camera_videos(id),
                status VARCHAR(20) NOT NULL DEFAULT 'queued',
                ticket_id INTEGER REFERENCES tickets(id),
                error_message TEXT,
                latitude FLOAT,
                longitude FLOAT,
                captured_at TIMESTAMPTZ,
                license_plate VARCHAR(20) DEFAULT 'TBD',
                violation_zone VARCHAR(20) DEFAULT 'red_white',
                description TEXT,
                submitted_by VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """))
        conn.commit()
    print("upload_jobs table ready (PostgreSQL)")


def migrate_sqlite():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS upload_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_video_id INTEGER NOT NULL REFERENCES camera_videos(id),
                status VARCHAR(20) NOT NULL DEFAULT 'queued',
                ticket_id INTEGER REFERENCES tickets(id),
                error_message TEXT,
                latitude REAL,
                longitude REAL,
                captured_at TIMESTAMP,
                license_plate VARCHAR(20) DEFAULT 'TBD',
                violation_zone VARCHAR(20) DEFAULT 'red_white',
                description TEXT,
                submitted_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """))
        conn.commit()
    print("upload_jobs table ready (SQLite)")


def migrate():
    if "sqlite" in db_url.lower():
        migrate_sqlite()
    else:
        migrate_postgres()


if __name__ == "__main__":
    migrate()
