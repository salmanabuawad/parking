"""Map basemap configuration for the frontend. Exposes the MapTiler key (if set) so the cameras map
can use MapTiler vector tiles; the key is public by design (browser fetches tiles with it), so
restrict it by allowed origins in the MapTiler dashboard. Empty key → frontend uses OSM fallback.
"""
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/config")
def map_config():
    key = settings.maptiler_key or ""
    return {
        "maptiler_key": key,
        "style_url": (f"https://api.maptiler.com/maps/streets-v2/style.json?key={key}" if key else None),
    }
