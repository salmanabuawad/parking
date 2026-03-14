from sqlalchemy import text

from app.database import engine

DDL = """
CREATE TABLE IF NOT EXISTS ticket_screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    frame_time_sec FLOAT NULL,
    captured_at DATETIME NULL,
    created_by VARCHAR(50) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ticket_screenshots_ticket_id ON ticket_screenshots(ticket_id);
"""

with engine.begin() as conn:
    for statement in [s.strip() for s in DDL.split(';') if s.strip()]:
        conn.execute(text(statement))

print('ticket_screenshots migration applied')
