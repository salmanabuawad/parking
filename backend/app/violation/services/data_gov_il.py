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
