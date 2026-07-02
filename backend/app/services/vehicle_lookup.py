"""Single source of truth for turning a data.gov.il vehicle record into the ticket's display fields.

Replaces the worker's older two-step lookup (local sample CSV + a separate data.gov.il call) and the
inline mapping in inspector_review_service. The one registry path is app.services.vehicle_registry_api
(configurable via app_config); callers that already hold a record just map it.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def record_to_vehicle_fields(record: dict | None) -> dict[str, Any]:
    """Map a data.gov.il record to {vehicle_make, vehicle_model, vehicle_year, vehicle_color,
    vehicle_type}; {} for no record."""
    if not record:
        return {}
    out: dict[str, Any] = {}
    make = record.get("tozeret_nm") or record.get("manufacturer")
    model = record.get("kinuy_mishari") or record.get("degem_nm") or record.get("model")
    color = record.get("tzeva_rechev") or record.get("color")
    vtype = record.get("sug_degem") or record.get("vehicle_type")
    if make:
        out["vehicle_make"] = make
    if model:
        out["vehicle_model"] = model
    if color:
        out["vehicle_color"] = color
    if vtype:
        out["vehicle_type"] = vtype
    year = record.get("shnat_yitzur")
    if year is None:
        year = record.get("year")
    if year is not None:
        try:
            out["vehicle_year"] = int(year)
        except (ValueError, TypeError):
            pass
    return out


def lookup_vehicle_fields(db: Session, plate: str) -> dict[str, Any]:
    """Look a plate up in the registry and return its display fields (or {})."""
    if not plate or plate == "11111":
        return {}
    try:
        from app.services.vehicle_registry_api import lookup_vehicle_by_plate
        r = lookup_vehicle_by_plate(db, plate)
        if r.get("status") == "plate_found":
            return record_to_vehicle_fields(r.get("record"))
    except Exception:
        pass
    return {}
