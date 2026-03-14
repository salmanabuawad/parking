"""Create ticket_screenshots table for blurred screenshot evidence attachments."""

from sqlalchemy import text

from app.database import engine


def migrate_postgres() -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_screenshots (
                id SERIAL PRIMARY KEY,
                ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
                storage_path VARCHAR(500) NOT NULL,
                frame_time_seconds DOUBLE PRECISION NOT NULL,
                video_timestamp TIMESTAMPTZ NULL,
                source_video_id VARCHAR(100) NULL,
                created_by VARCHAR(50) NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_screenshots_ticket_id ON ticket_screenshots(ticket_id)"))
        conn.commit()
        print("ticket_screenshots table ready (PostgreSQL)")


def migrate_sqlite() -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
                storage_path VARCHAR(500) NOT NULL,
                frame_time_seconds REAL NOT NULL,
                video_timestamp TIMESTAMP NULL,
                source_video_id VARCHAR(100) NULL,
                created_by VARCHAR(50) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_screenshots_ticket_id ON ticket_screenshots(ticket_id)"))
        conn.commit()
        print("ticket_screenshots table ready (SQLite)")


def migrate() -> None:
    db_url = str(engine.url).lower()
    if "sqlite" in db_url:
        migrate_sqlite()
    else:
        migrate_postgres()


if __name__ == "__main__":
    migrate()
