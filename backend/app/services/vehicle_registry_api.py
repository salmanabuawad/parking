"""Israeli vehicle registry lookup via configurable data.gov.il CKAN API."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AppConfig, VehicleRegistryCache


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


# --- §13 lookup cache -------------------------------------------------------------
# Cache I/O uses its own short-lived session so a cache read/write can never flush,
# commit, or roll back the caller's in-flight transaction (inspector save / worker
# finalization). Both helpers swallow all errors — the cache is best-effort.

def _cache_get(plate: str, ttl_hours: int) -> dict[str, Any] | None:
    """Return {status, record} for a fresh cached lookup, else None. Never raises."""
    if ttl_hours <= 0:
        return None
    s = SessionLocal()
    try:
        row = s.query(VehicleRegistryCache).filter(VehicleRegistryCache.plate == plate).first()
        if not row or row.fetched_at is None:
            return None
        fetched = row.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - fetched > timedelta(hours=ttl_hours):
            return None
        return {"status": row.status, "record": row.record_json}
    except Exception:
        return None
    finally:
        s.close()


def _cache_put(plate: str, status: str, record: dict | None) -> None:
    """Upsert a definitive lookup result. Never raises; isolated from the caller's txn."""
    s = SessionLocal()
    try:
        row = s.query(VehicleRegistryCache).filter(VehicleRegistryCache.plate == plate).first()
        now = datetime.now(timezone.utc)
        if row:
            row.status = status
            row.record_json = record
            row.fetched_at = now
        else:
            s.add(VehicleRegistryCache(plate=plate, status=status, record_json=record, fetched_at=now))
        s.commit()
    except Exception:
        try:
            s.rollback()
        except Exception:
            pass
    finally:
        s.close()


def lookup_vehicle_by_plate(db: Session, plate_number: str) -> dict[str, Any]:
    """Lookup plate in data.gov.il using app_config API settings.

    Returns a normalized status object and never raises for API/data errors. Definitive
    results (plate_found / plate_not_found) are served from and written to a TTL cache
    (#13); transient lookup_failed responses are never cached so the next call retries.
    """
    settings = get_vehicle_registry_config(db)
    plate = normalize_israeli_plate(plate_number)

    if not settings["enabled"]:
        return {"status": "disabled", "plate": plate, "record": None}

    if len(plate) not in (7, 8):
        return {"status": "invalid_plate_format", "plate": plate, "record": None}

    cached = _cache_get(plate, settings["cache_ttl_hours"])
    if cached is not None:
        return {"status": cached["status"], "plate": plate, "record": cached["record"], "cached": True}

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
            _cache_put(plate, "plate_not_found", None)
            return {"status": "plate_not_found", "plate": plate, "record": None}
        _cache_put(plate, "plate_found", records[0])
        return {"status": "plate_found", "plate": plate, "record": records[0]}
    except Exception as exc:  # keep ticket pipeline alive if gov API is down
        return {
            "status": "lookup_failed",
            "plate": plate,
            "record": None,
            "error": str(exc),
        }
