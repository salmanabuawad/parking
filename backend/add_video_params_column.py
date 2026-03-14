"""Add video_params (JSON) to tickets table for extracted video metadata (GPS, duration, etc.)."""
from sqlalchemy import text
from app.database import engine


def migrate():
    last_err = None
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS video_params JSONB",  # PostgreSQL
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS video_params JSON",  # PostgreSQL / MySQL
            "ALTER TABLE tickets ADD COLUMN video_params JSON",  # SQLite
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
                print("Added video_params column")
                return
            except Exception as e:
                conn.rollback()
                last_err = e
    if last_err:
        print("Could not add video_params:", last_err)


if __name__ == "__main__":
    migrate()
