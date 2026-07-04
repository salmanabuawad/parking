"""Real street names per city from OpenStreetMap (Overpass), cached to disk. Demo cameras are placed
on these actual named streets so their addresses are real, not generic invented names. Query once per
city (slow + rate-limited), then reuse the cache. Falls back to an empty list (→ no street) on error.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from app.config import settings

OVERPASS = "https://overpass-api.de/api/interpreter"
HIGHWAYS = "residential|primary|secondary|tertiary|unclassified|living_street|trunk|road|pedestrian"


def _dir() -> Path:
    d = Path(settings.videos_dir) / "map_cache" / "streets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fetch(bbox) -> list[dict]:
    """bbox = [[west, south], [east, north]]. Returns sample points {name, lat, lng} along named
    streets in the bbox."""
    (w, s), (e, n) = bbox
    # Union ways that carry any of these name tags — some places (e.g. Golan Druze villages) tag only
    # name:ar / name:he without a plain `name`.
    parts = "".join(
        f'way["highway"~"^({HIGHWAYS})$"]["{k}"]({s},{w},{n},{e});'
        for k in ("name", "name:he", "name:ar")
    )
    query = f"[out:json][timeout:50];({parts});out geom;"
    try:
        r = requests.post(OVERPASS, data={"data": query}, timeout=60,
                          headers={"User-Agent": "advancedparking/1.0"})
        if r.status_code != 200:
            return []
        elements = r.json().get("elements", [])
    except Exception:
        return []
    pts: list[dict] = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name:he") or tags.get("name") or tags.get("name:ar") or tags.get("name:en")
        geom = el.get("geometry") or []
        if not name or not geom:
            continue
        sample = geom if len(geom) <= 3 else [geom[0], geom[len(geom) // 2], geom[-1]]
        for p in sample:
            pts.append({"name": name, "lat": p["lat"], "lng": p["lon"]})
    return pts


def get_streets(city_key: str, bbox, refresh: bool = False) -> list[dict]:
    """Street sample points for a city; cached to disk after the first Overpass call."""
    p = _dir() / f"{city_key}.json"
    if p.exists() and not refresh:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    pts = _fetch(bbox)
    if pts:
        p.write_text(json.dumps(pts, ensure_ascii=False), encoding="utf-8")
    return pts
