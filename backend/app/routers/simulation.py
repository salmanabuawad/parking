"""Simulation API — use bundled sample clips as stand-in cameras so the whole camera-zone
configuration flow can be exercised without live RTSP hardware.

``POST /simulation/cameras`` seeds one camera per clip (extracting a calibration snapshot from the
clip); the zone configurator then draws enforcement sections on that snapshot exactly as it would for
a real camera. Idempotent by ``simulation_source`` — re-running refreshes the snapshot, not creates
duplicates. A simulation camera can re-grab a fresh (random) frame via the normal snapshot endpoint.
"""
import random
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_camera_repo
from app.models import Camera
from app.repositories import CameraRepository
from app.services import city_streets, simulation as sim
from app.services.cities import load_cities, random_point_in, street_bbox

router = APIRouter(prefix="/simulation", tags=["simulation"])

# Spread simulation cameras across a few real Netanya street locations (lat, lng).
NETANYA_SPOTS = [
    (32.32755, 34.85493),  # city center / Herzl St
    (32.32148, 34.85806),  # near Independence Square
    (32.31690, 34.86075),  # south Netanya
    (32.33012, 34.86010),  # north
    (32.32430, 34.85190),  # toward the beach
    (32.31450, 34.85520),
]


@router.get("/sources")
def list_sources():
    """List the available simulation clips (videos/simulation/*.mp4)."""
    return sim.list_sources()


class SeedRequest(BaseModel):
    sources: list[str] | None = None   # None → every available clip
    seek_frac: float | None = 0.4      # where in each clip to grab the calibration frame (0..1)


def _existing_sim_camera(camera_repo: CameraRepository, source: str):
    for c in camera_repo.get_all():
        if (c.connection_config or {}).get("simulation_source") == source:
            return c
    return None


def _save_snapshot(camera_id: int, jpeg: bytes) -> str:
    rel = f"camera_snapshots/camera_{camera_id}.jpg"
    dest = Path(settings.videos_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(jpeg)
    return rel


@router.post("/cameras")
def seed_cameras(
    body: SeedRequest | None = None,
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Create (or refresh) a simulation camera for each requested clip, extracting a calibration
    snapshot from it. Returns the affected cameras."""
    body = body or SeedRequest()
    names = body.sources or [s["name"] for s in sim.list_sources()]
    if not names:
        raise HTTPException(status_code=404, detail="לא נמצאו קבצי סימולציה בשרת (videos/simulation/*.mp4)")

    out = []
    for idx, name in enumerate(names):
        got = sim.frame_for_source(name, seek_frac=body.seek_frac)
        if not got:
            continue
        jpeg, w, h = got
        cam = _existing_sim_camera(camera_repo, name)
        if cam is None:
            cam = camera_repo.create(
                name=f"סימולציה {name.upper()}",
                location="נתניה",
                connection_type="simulation",
                connection_config={"simulation_source": name},
                source_type="simulation",
                is_active=True,
            )
        rel = _save_snapshot(cam.id, jpeg)
        fields = {
            "snapshot_path": rel,
            "calibration_width": w,
            "calibration_height": h,
            "source_type": "simulation",
            "city": "netanya",
        }
        # Place on the Netanya map if not already positioned (never override a moved camera)
        if cam.latitude is None or cam.longitude is None:
            lat, lng = NETANYA_SPOTS[idx % len(NETANYA_SPOTS)]
            fields["latitude"] = lat
            fields["longitude"] = lng
        camera_repo.update(cam.id, **fields)
        out.append({"id": cam.id, "name": cam.name, "source": name, "width": w, "height": h,
                    "latitude": fields.get("latitude", cam.latitude),
                    "longitude": fields.get("longitude", cam.longitude)})

    if not out:
        raise HTTPException(status_code=400, detail="לא ניתן לחלץ פריים מאף קליפ סימולציה")
    return {"cameras": out, "count": len(out)}


# ── Sample fleet generator (multi-city dashboard demo data) ───────────────────
# Weighted status pool: ~70% online, 15% offline, 10% maintenance, 5% error
FLEET_STATUS_POOL = (["online"] * 70) + (["offline"] * 15) + (["maintenance"] * 10) + (["error"] * 5)

# Relative city size (≈ population, thousands) — the demo camera count scales with this, so bigger
# cities get more cameras. count ≈ size * FLEET_SCALE, but at least FLEET_FLOOR per city.
CITY_SIZE = {"netanya": 230, "haifa": 285, "tel-aviv": 470, "jerusalem": 950, "tiberias": 45, "bukata": 7}
FLEET_SCALE = 0.04
FLEET_FLOOR = 6


def _city_camera_count(key: str, override: int | None) -> int:
    if override:
        return max(1, min(1000, override))
    return max(FLEET_FLOOR, round(CITY_SIZE.get(key, 100) * FLEET_SCALE))

# Cities (center, zoom, bounds) now live in the DB `cities` table — see app.services.cities and the
# /cities router. Demo-fleet placement derives points from each city's bounds.


class FleetRequest(BaseModel):
    count: int | None = None            # cameras per city; None → scale by city size
    cities: list[str] | None = None     # None → all cities
    clear: bool = True                  # remove previously generated demo cameras for those cities


@router.post("/generate-fleet")
def generate_fleet(
    body: FleetRequest | None = None,
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Generate `count` demo cameras per city (varied status), spread on-land across each city, for the
    fleet dashboard. Tagged connection_config.generated=true + city=<key>; clear=true first removes the
    previous generated batch for the requested cities so they don't accumulate."""
    body = body or FleetRequest()
    db = camera_repo.db
    cmap = {c.key: c for c in load_cities(db)}          # active cities, keyed by slug
    keys = [k for k in (body.cities or list(cmap.keys())) if k in cmap]
    if not keys:
        raise HTTPException(status_code=400, detail="No valid cities requested")

    removed = 0
    if body.clear:
        target = set(keys)
        existing = [
            c for c in db.query(Camera).all()
            if (c.connection_config or {}).get("generated") and (c.city or "netanya") in target
        ]
        for c in existing:
            db.delete(c)
            removed += 1
        if existing:
            db.commit()

    objs = []
    for key in keys:
        city = cmap[key]
        label = city.label
        streets = city_streets.get_streets(key, street_bbox(city))  # real OSM street names (cached)
        for i in range(1, _city_camera_count(key, body.count) + 1):
            status = random.choice(FLEET_STATUS_POOL)
            if streets:
                st = random.choice(streets)  # place on a real street, keep its real name
                lat = round(st["lat"] + random.uniform(-0.00015, 0.00015), 6)
                lng = round(st["lng"] + random.uniform(-0.00015, 0.00015), 6)
                location = f"{st['name']} {random.randint(1, 120)}, {label}"
            else:
                lat, lng = random_point_in(city)
                location = label
            objs.append(Camera(
                name=f"{label} {i:03d}",
                location=location,
                connection_type="ip",
                connection_config={"generated": True},
                source_type="uploaded_image",
                is_active=(status != "offline"),
                status=status,
                city=key,
                latitude=lat,
                longitude=lng,
            ))
    db.add_all(objs)
    db.commit()
    return {"created": len(objs), "removed": removed, "cities": keys,
            "by_status": dict(Counter(o.status for o in objs))}
