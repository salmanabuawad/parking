"""Add temporal blur settings to app_config.

Note: blur_kernel_size already exists in app_config in the current repo, so this
migration only adds the new temporal-blur-related fields and ensures a config row
exists.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text

from app.database import engine


db_url = str(engine.url)


def has_column(conn, table: str, column: str) -> bool:
    if "sqlite" in db_url.lower():
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table, "column_name": column},
    ).fetchall()
    return bool(rows)


def migrate():
    with engine.connect() as conn:
        if not has_column(conn, "app_config", "blur_expand_ratio"):
            conn.execute(text("ALTER TABLE app_config ADD COLUMN blur_expand_ratio FLOAT DEFAULT 0.18"))
        if not has_column(conn, "app_config", "temporal_blur_enabled"):
            conn.execute(text("ALTER TABLE app_config ADD COLUMN temporal_blur_enabled BOOLEAN DEFAULT 1"))
        if not has_column(conn, "app_config", "temporal_blur_max_misses"):
            conn.execute(text("ALTER TABLE app_config ADD COLUMN temporal_blur_max_misses INTEGER DEFAULT 6"))

        conn.execute(
            text(
                """
                INSERT INTO app_config (id, blur_kernel_size, blur_expand_ratio, temporal_blur_enabled, temporal_blur_max_misses, use_violation_pipeline)
                SELECT 1, 15, 0.18, 1, 6, 1
                WHERE NOT EXISTS (SELECT 1 FROM app_config)
                """
            )
        )
        conn.commit()

    print("app_config temporal blur settings ready")


if __name__ == "__main__":
    migrate()
