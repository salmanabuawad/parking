"""
Ministry of Transport vehicle registry via data.gov.il API.
Dataset: https://data.gov.il/he/datasets/ministry_of_transport/private-and-commercial-vehicles/053cea08-09bc-40ec-8f7a-156f0677aff3
Uses CKAN datastore_search when local registry does not have the plate.
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Optional

from app.config import settings
from app.violation.utils.text import normalize_plate_text


def _plate_exists_via_api(plate_number: str) -> Optional[bool]:
    """
    Check if plate exists in data.gov.il MoT dataset via CKAN datastore_search.
    Returns True if found, False if not found, None if API unavailable (e.g. 403, timeout).
    """
    plate = normalize_plate_text(plate_number)
    if not plate or len(plate) < 7:
        return False
    resource_id = getattr(settings, "data_gov_il_resource_id", None) or "053cea08-09bc-40ec-8f7a-156f0677aff3"
    base_url = "https://data.gov.il/api/3/action/datastore_search"
    # CKAN: filters as JSON object for exact match on mispar_rechev (plate column)
    filters = json.dumps({"mispar_rechev": plate})
    url = f"{base_url}?resource_id={resource_id}&filters={urllib.parse.quote(filters)}&limit=1"
    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("success"):
            return None
        records = data.get("result", {}).get("records", [])
        return len(records) > 0
    except Exception:
        return None


def data_gov_il_plate_exists(plate_number: str) -> Optional[bool]:
    """
    Check if plate exists in Ministry of Transport registry (data.gov.il).
    Returns True if found, False if not found, None if check could not be performed.
    """
    return _plate_exists_via_api(plate_number)


def data_gov_il_lookup(plate_number: str) -> Optional[dict]:
    """
    Fetch vehicle record from data.gov.il MoT dataset.
    Returns a dict with keys: manufacturer, model_name, year, color, vehicle_type, raw
    or None if not found / API unavailable.

    Known data.gov.il columns (may vary by dataset version):
      mispar_rechev, tozeret_nm, kinuy_mishari, shnat_yitzur,
      tzeva_rechev (color), SUG_DEGEM (vehicle type code), degem_manoa
    """
    plate = normalize_plate_text(plate_number)
    if not plate or len(plate) < 7:
        return None
    resource_id = getattr(settings, "data_gov_il_resource_id", None) or "053cea08-09bc-40ec-8f7a-156f0677aff3"
    base_url = "https://data.gov.il/api/3/action/datastore_search"
    filters = json.dumps({"mispar_rechev": plate})
    url = f"{base_url}?resource_id={resource_id}&filters={urllib.parse.quote(filters)}&limit=1"
    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("success"):
            return None
        records = data.get("result", {}).get("records", [])
        if not records:
            return None
        rec = records[0]
        return {
            "manufacturer": str(rec.get("tozeret_nm", "") or "").strip() or None,
            "model_name":   str(rec.get("kinuy_mishari", "") or "").strip() or None,
            "year":         _safe_int(rec.get("shnat_yitzur")),
            "color":        str(rec.get("tzeva_rechev", "") or "").strip() or None,
            "vehicle_type": str(rec.get("SUG_DEGEM", "") or "").strip() or None,
            "raw":          rec,
        }
    except Exception:
        return None


def _safe_int(val) -> Optional[int]:
    try:
        return int(float(val)) if val is not None else None
    except (TypeError, ValueError):
        return None
