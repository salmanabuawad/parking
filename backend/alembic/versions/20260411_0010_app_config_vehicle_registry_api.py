"""Add vehicle registry API settings to app_config.

Revision ID: 20260411_0010
Revises: 20260411_0009
Create Date: 2026-04-11
"""
from alembic import op
from sqlalchemy import text

revision = "20260411_0010"
down_revision = "20260411_0009"
branch_labels = None
depends_on = None


DEFAULT_API_URL = "https://data.gov.il/api/3/action/datastore_search"
DEFAULT_RESOURCE_ID = "053cea08-09bc-40ec-8f7a-156f0677aff3"
DEFAULT_PLATE_FIELD = "mispar_rechev"


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS vehicle_registry_api_enabled BOOLEAN DEFAULT TRUE NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS vehicle_registry_api_url VARCHAR(500)
            DEFAULT '{DEFAULT_API_URL}' NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS vehicle_registry_resource_id VARCHAR(80)
            DEFAULT '{DEFAULT_RESOURCE_ID}' NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS vehicle_registry_plate_field VARCHAR(80)
            DEFAULT '{DEFAULT_PLATE_FIELD}' NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS vehicle_registry_timeout_seconds INTEGER DEFAULT 10 NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE app_config
            ADD COLUMN IF NOT EXISTS vehicle_registry_cache_ttl_hours INTEGER DEFAULT 24 NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE app_config
            SET vehicle_registry_api_enabled = COALESCE(vehicle_registry_api_enabled, TRUE),
                vehicle_registry_api_url = COALESCE(vehicle_registry_api_url, :api_url),
                vehicle_registry_resource_id = COALESCE(vehicle_registry_resource_id, :resource_id),
                vehicle_registry_plate_field = COALESCE(vehicle_registry_plate_field, :plate_field),
                vehicle_registry_timeout_seconds = COALESCE(vehicle_registry_timeout_seconds, 10),
                vehicle_registry_cache_ttl_hours = COALESCE(vehicle_registry_cache_ttl_hours, 24)
            """
        ),
        {
            "api_url": DEFAULT_API_URL,
            "resource_id": DEFAULT_RESOURCE_ID,
            "plate_field": DEFAULT_PLATE_FIELD,
        },
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS vehicle_registry_cache_ttl_hours"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS vehicle_registry_timeout_seconds"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS vehicle_registry_plate_field"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS vehicle_registry_resource_id"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS vehicle_registry_api_url"))
    conn.execute(text("ALTER TABLE app_config DROP COLUMN IF EXISTS vehicle_registry_api_enabled"))
