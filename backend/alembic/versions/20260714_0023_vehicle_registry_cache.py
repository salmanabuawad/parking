"""Vehicle registry lookup cache (#13): vehicle_registry_cache table.

Caches definitive data.gov.il lookups (plate_found / plate_not_found) keyed by
normalized plate, so the deep-check fan-out and inspector saves stop re-hitting the
gov API. Freshness is governed by app_config.vehicle_registry_cache_ttl_hours.

Revision ID: 20260714_0023
Revises: 20260713_0022
Create Date: 2026-07-14
"""
from alembic import op

revision = "20260714_0023"
down_revision = "20260713_0022"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle_registry_cache (
            id SERIAL PRIMARY KEY,
            plate VARCHAR(20) NOT NULL,
            status VARCHAR(40) NOT NULL,
            record_json JSONB,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_vehicle_registry_cache_plate "
        "ON vehicle_registry_cache (plate)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS vehicle_registry_cache")
