"""Add latitude, longitude, captured_at to tickets table."""
from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        for col, stmt in [
            ("latitude", "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION"),
            ("longitude", "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION"),
            ("captured_at", "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS captured_at TIMESTAMP WITH TIME ZONE"),
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
                print(f"Added {col} column")
            except Exception as e:
                print(f"{col}: {e}")
                conn.rollback()

if __name__ == "__main__":
    migrate()
