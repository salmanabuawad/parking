"""Idempotent migration for app_config vehicle registry API settings.

Use this only if you are not using Alembic:
    python migrate_app_config_vehicle_registry_api.py
"""
from sqlalchemy import text

from app.database import engine


DEFAULT_API_URL = "https://data.gov.il/api/3/action/datastore_search"
DEFAULT_RESOURCE_ID = "053cea08-09bc-40ec-8f7a-156f0677aff3"
DEFAULT_PLATE_FIELD = "mispar_rechev"


SQL = """
ALTER TABLE app_config
ADD COLUMN IF NOT EXISTS vehicle_registry_api_enabled BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE app_config
ADD COLUMN IF NOT EXISTS vehicle_registry_api_url VARCHAR(500) DEFAULT 'https://data.gov.il/api/3/action/datastore_search' NOT NULL;
ALTER TABLE app_config
ADD COLUMN IF NOT EXISTS vehicle_registry_resource_id VARCHAR(80) DEFAULT '053cea08-09bc-40ec-8f7a-156f0677aff3' NOT NULL;
ALTER TABLE app_config
ADD COLUMN IF NOT EXISTS vehicle_registry_plate_field VARCHAR(80) DEFAULT 'mispar_rechev' NOT NULL;
ALTER TABLE app_config
ADD COLUMN IF NOT EXISTS vehicle_registry_timeout_seconds INTEGER DEFAULT 10 NOT NULL;
ALTER TABLE app_config
ADD COLUMN IF NOT EXISTS vehicle_registry_cache_ttl_hours INTEGER DEFAULT 24 NOT NULL;
"""


if __name__ == "__main__":
    with engine.begin() as conn:
        conn.execute(text(SQL))
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
    print("app_config vehicle registry API settings migrated.")
