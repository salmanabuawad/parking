"""Add violation analysis columns to tickets table if missing."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine

COLUMNS = [
    ("violation_rule_id",         "VARCHAR(30)"),
    ("violation_decision",        "VARCHAR(30)"),
    ("violation_confidence",      "FLOAT"),
    ("violation_description_he",  "TEXT"),
    ("violation_description_en",  "TEXT"),
]


def migrate():
    with engine.connect() as conn:
        for col_name, col_type in COLUMNS:
            r = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tickets' AND column_name = :col
            """), {"col": col_name})
            if r.fetchone():
                print(f"  {col_name}: already exists, skipping")
            else:
                conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}"))
                print(f"  {col_name}: added")
        conn.commit()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
