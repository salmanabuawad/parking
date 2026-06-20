"""Israeli vehicle registry lookup via configurable data.gov.il CKAN API."""
from __future__ import annotations

import json
import re
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.models import AppConfig


def normalize_israeli_plate(value: str) -> str:
    """Normalize Israeli plate OCR to digits only."""
    return re.sub(r"\D", "", str(value or ""))


def get_vehicle_registry_config(db: Session) -> dict[str, Any]:
    """Return app_config vehicle registry API settings with safe defaults."""
    cfg = db.query(AppConfig).first()
    return {
        "enabled": True if cfg is None else bool(cfg.vehicle_registry_api_enabled),
        "api_url": (cfg.vehicle_registry_api_url if cfg else None)
        or "https://data.gov.il/api/3/action/datastore_search",
        "resource_id": (cfg.vehicle_registry_resource_id if cfg else None)
        or "053cea08-09bc-40ec-8f7a-156f0677aff3",
        "plate_field": (cfg.vehicle_registry_plate_field if cfg else None) or "mispar_rechev",
        "timeout_seconds": int((cfg.vehicle_registry_timeout_seconds if cfg else None) or 10),
        "cache_ttl_hours": int((cfg.vehicle_registry_cache_ttl_hours if cfg else None) or 24),
    }


def lookup_vehicle_by_plate(db: Session, plate_number: str) -> dict[str, Any]:
    """Lookup plate in data.gov.il using app_config API settings.

    Returns a normalized status object and never raises for API/data errors.
    """
    settings = get_vehicle_registry_config(db)
    plate = normalize_israeli_plate(plate_number)

    if not settings["enabled"]:
        return {"status": "disabled", "plate": plate, "record": None}

    if len(plate) not in (7, 8):
        return {"status": "invalid_plate_format", "plate": plate, "record": None}

    params = {
        "resource_id": settings["resource_id"],
        "filters": json.dumps({settings["plate_field"]: plate}),
        "limit": 1,
    }

    try:
        response = requests.get(
            settings["api_url"],
            params=params,
            timeout=settings["timeout_seconds"],
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("result", {}).get("records", [])
        if not records:
            return {"status": "plate_not_found", "plate": plate, "record": None}
        return {"status": "plate_found", "plate": plate, "record": records[0]}
    except Exception as exc:  # keep ticket pipeline alive if gov API is down
        return {
            "status": "lookup_failed",
            "plate": plate,
            "record": None,
            "error": str(exc),
        }
