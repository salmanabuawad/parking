"""Map basemap for the frontend, served from a LOCAL cache of MapTiler.

The frontend loads `/api/map/style.json` (rewritten so every tile/font/sprite points back here). Each
resource is fetched from MapTiler once, stored on disk (see services/map_cache.py), and served locally
thereafter — so after a city is cached the map makes zero MapTiler calls. `POST /api/map/cache`
pre-downloads a city (or all cities). If no MAPTILER_KEY is set, /config returns null and the frontend
falls back to plain OSM raster tiles.
"""
import json

from fastapi import APIRouter, HTTPException, Request, Response

from app.config import settings
from app.services import map_cache

router = APIRouter(prefix="/map", tags=["map"])

_TILE_HEADERS = {"Cache-Control": "public, max-age=604800"}
_ASSET_HEADERS = {"Cache-Control": "public, max-age=2592000"}


def _map_base(request: Request) -> str:
    """Absolute base URL for our map endpoints, e.g. https://parking.wavelync.com/api/map."""
    if settings.public_base_url:
        return settings.public_base_url.rstrip("/") + "/api/map"
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/map"


@router.get("/config")
def map_config(request: Request):
    """Basemap config for the frontend. style_url points at our locally-cached style (when a MapTiler
    key is configured); empty → the frontend uses the OSM raster fallback."""
    if not settings.maptiler_key:
        return {"maptiler_key": "", "style_url": None}
    return {"maptiler_key": settings.maptiler_key, "style_url": f"{_map_base(request)}/style.json"}


@router.get("/style.json")
def map_style(request: Request):
    style = map_cache.local_style(_map_base(request))
    if not style:
        raise HTTPException(status_code=503, detail="Map style unavailable (no MapTiler key?)")
    return Response(content=json.dumps(style), media_type="application/json",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/tiles/{z}/{x}/{yfile}")
def map_tile(z: int, x: int, yfile: str):
    try:
        y = int(yfile.split(".")[0])
    except ValueError:
        raise HTTPException(status_code=404, detail="tile")
    data = map_cache.get_tile(z, x, y)
    if not data:  # None (unavailable) or b"" (cached 404) → no tile here
        raise HTTPException(status_code=404, detail="tile")
    return Response(content=data, media_type="application/x-protobuf", headers=_TILE_HEADERS)


@router.get("/fonts/{fontstack}/{rngfile}")
def map_font(fontstack: str, rngfile: str):
    data = map_cache.get_font(fontstack, rngfile.split(".")[0])
    if not data:
        raise HTTPException(status_code=404, detail="font")
    return Response(content=data, media_type="application/x-protobuf", headers=_ASSET_HEADERS)


@router.get("/sprite/{name}")
def map_sprite(name: str):
    data = map_cache.get_sprite(name)
    if not data:
        raise HTTPException(status_code=404, detail="sprite")
    ct = "application/json" if name.endswith(".json") else "image/png"
    return Response(content=data, media_type=ct, headers=_ASSET_HEADERS)


@router.post("/cache")
def warm_cache(body: dict | None = None):
    """Pre-download map data for cities so the whole map is on disk. Body {cities:[...]} → those
    cities; omitted → all. Idempotent (cached resources are skipped)."""
    if not settings.maptiler_key:
        raise HTTPException(status_code=400, detail="No MAPTILER_KEY configured")
    from app.routers.simulation import CITIES, _city_bounds, _street_bbox
    from app.services import city_streets
    wanted = (body or {}).get("cities") or list(CITIES.keys())
    out = {}
    for key in wanted:
        if key in CITIES:
            stats = map_cache.warm_city(_city_bounds(CITIES[key]))
            stats["streets"] = len(city_streets.get_streets(key, _street_bbox(key)))  # real OSM names
            out[key] = stats
    return {"cities": out, "cache": map_cache.cache_size()}
