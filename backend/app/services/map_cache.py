"""Local MapTiler cache. Fetch each city's vector tiles / fonts / sprite / style from MapTiler ONCE,
store them on disk, then serve everything from our own backend so the map needs no further MapTiler
calls. OpenMapTiles vector tiles top out at z14 (MapLibre over-zooms beyond that), and each city is a
small bbox, so a whole city is only ~20 tiles — the cache stays tiny.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import quote

import requests

from app.config import settings

MAPTILER = "https://api.maptiler.com"
STYLE_PATH = "maps/streets-v2/style.json"
SPRITE_BASE = "maps/streets-v2"
TIMEOUT = 20
FONT_RANGES = ["0-255", "256-511", "512-767", "1024-1279", "1280-1535", "8192-8447"]


def cache_dir() -> Path:
    d = Path(settings.videos_dir) / "map_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key() -> str:
    return settings.maptiler_key or ""


def _cached_or_fetch(rel: str, url: str, allow_missing: bool = False) -> bytes | None:
    """Return cached bytes at cache_dir/rel; else fetch url once, store, return. b"" marks a cached
    404 (so we never re-hit MapTiler for a missing tile). None = unavailable (no key / error)."""
    p = cache_dir() / rel
    if p.exists():
        return p.read_bytes()
    if not _key():
        return None
    try:
        r = requests.get(url, timeout=TIMEOUT)
    except Exception:
        return None
    if r.status_code == 404 and allow_missing:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        return b""
    if r.status_code != 200:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)  # requests transparently gunzips content-encoding; MapLibre reads either
    return r.content


def get_tile(z: int, x: int, y: int) -> bytes | None:
    return _cached_or_fetch(f"tiles/{z}/{x}/{y}.pbf",
                            f"{MAPTILER}/tiles/v3/{z}/{x}/{y}.pbf?key={_key()}", allow_missing=True)


def get_font(fontstack: str, rng: str) -> bytes | None:
    safe = fontstack.replace("/", "_").replace("..", "_")
    return _cached_or_fetch(f"fonts/{safe}/{rng}.pbf",
                            f"{MAPTILER}/fonts/{quote(fontstack, safe=',')}/{rng}.pbf?key={_key()}",
                            allow_missing=True)


def get_sprite(name: str) -> bytes | None:
    safe = name.replace("/", "_")
    return _cached_or_fetch(f"sprite/{safe}", f"{MAPTILER}/{SPRITE_BASE}/{name}?key={_key()}", allow_missing=True)


def _original_style() -> dict | None:
    raw = _cached_or_fetch("style_orig.json", f"{MAPTILER}/{STYLE_PATH}?key={_key()}")
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _vector_zooms() -> tuple[int, int]:
    raw = _cached_or_fetch("tiles_v3.json", f"{MAPTILER}/tiles/v3/tiles.json?key={_key()}")
    if raw:
        try:
            tj = json.loads(raw)
            return int(tj.get("minzoom", 0)), int(tj.get("maxzoom", 14))
        except Exception:
            pass
    return 0, 14


def local_style(base: str) -> dict | None:
    """MapTiler streets-v2 style rewritten so every resource is served from our backend `{base}`
    (e.g. https://host/api/map). Returns None if the original style can't be fetched."""
    style = _original_style()
    if not style:
        return None
    minz, maxz = _vector_zooms()
    for src in (style.get("sources") or {}).values():
        if src.get("type") == "vector":
            src.pop("url", None)
            src["tiles"] = [f"{base}/tiles/{{z}}/{{x}}/{{y}}.pbf"]
            src["minzoom"] = minz
            src["maxzoom"] = maxz
    style["glyphs"] = f"{base}/fonts/{{fontstack}}/{{range}}.pbf"
    style["sprite"] = f"{base}/sprite/sprite"
    return style


def _font_stacks() -> list[str]:
    style = _original_style() or {}
    stacks = set()
    for layer in style.get("layers", []):
        f = (layer.get("layout") or {}).get("text-font")
        if isinstance(f, list) and all(isinstance(x, str) for x in f):
            stacks.add(",".join(f))
    return sorted(stacks)


def _deg2tile(lat: float, lng: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def warm_city(bounds, minzoom: int = 9, maxzoom: int = 14) -> dict:
    """Fetch every tile in the city's bbox (z=minzoom..maxzoom) + the style, sprite and font ranges,
    so the whole city is on disk. bounds = [[west, south], [east, north]]."""
    (w, s), (e, n) = bounds
    _, vmax = _vector_zooms()
    maxzoom = min(maxzoom, vmax)
    tiles = 0
    for z in range(minzoom, maxzoom + 1):
        x_w, y_n = _deg2tile(n, w, z)
        x_e, y_s = _deg2tile(s, e, z)
        for x in range(min(x_w, x_e), max(x_w, x_e) + 1):
            for y in range(min(y_n, y_s), max(y_n, y_s) + 1):
                if get_tile(z, x, y):
                    tiles += 1
    for nm in ("sprite@2x.png", "sprite@2x.json", "sprite.png", "sprite.json"):
        get_sprite(nm)
    fonts = sum(1 for st in _font_stacks() for rg in FONT_RANGES if get_font(st, rg))
    return {"tiles": tiles, "fonts": fonts}


def cache_size() -> dict:
    files = total = 0
    for p in cache_dir().rglob("*"):
        if p.is_file():
            files += 1
            total += p.stat().st_size
    return {"files": files, "bytes": total}
