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
from app.services import simulation as sim

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
STREETS = [
    "הרצל", "ויצמן", "בן גוריון", "רזיאל", "סוקולוב", "אלנבי", "ז'בוטינסקי",
    "המלך ג'ורג'", "רוטשילד", "דיזנגוף", "החלוץ", "יפו", "בן יהודה", "הנביאים",
]
# Weighted status pool: ~70% online, 15% offline, 10% maintenance, 5% error
FLEET_STATUS_POOL = (["online"] * 70) + (["offline"] * 15) + (["maintenance"] * 10) + (["error"] * 5)

# Relative city size (≈ population, thousands) — the demo camera count scales with this, so bigger
# cities get more cameras. count ≈ size * FLEET_SCALE, but at least FLEET_FLOOR per city.
CITY_SIZE = {"netanya": 230, "haifa": 285, "tel-aviv": 470, "jerusalem": 950, "tiberias": 45}
FLEET_SCALE = 0.04
FLEET_FLOOR = 6


def _city_camera_count(key: str, override: int | None) -> int:
    if override:
        return max(1, min(1000, override))
    return max(FLEET_FLOOR, round(CITY_SIZE.get(key, 100) * FLEET_SCALE))

# City demo areas: a map center (lat, lng) + zoom and a set of ON-LAND anchor points across real
# neighborhoods; cameras scatter around anchors with a small jitter. `lng_min`/`lng_max` are
# water-avoidance clamps — coastal cities keep pins east of the sea, Tiberias west of the Kinneret.
CITIES: dict[str, dict] = {
    "netanya": {
        "label": "נתניה", "center": (32.3215, 34.8532), "zoom": 13, "lng_min": 34.855,
        "anchors": [
            (32.3286, 34.8590), (32.3240, 34.8615), (32.3320, 34.8600), (32.3340, 34.8635),
            (32.3190, 34.8600), (32.3155, 34.8640), (32.3110, 34.8615), (32.3070, 34.8648),
            (32.3040, 34.8605), (32.3270, 34.8648), (32.3210, 34.8662), (32.3140, 34.8632),
        ],
    },
    "haifa": {
        "label": "חיפה", "center": (32.7940, 34.9950), "zoom": 12, "lng_min": 34.978,
        "anchors": [
            (32.7940, 34.9896), (32.8080, 34.9970), (32.8160, 35.0010), (32.7870, 35.0030),
            (32.7830, 35.0130), (32.8010, 34.9950), (32.7780, 35.0080), (32.8050, 35.0060),
            (32.7920, 34.9990), (32.8120, 35.0040), (32.7990, 35.0100), (32.7890, 35.0050),
        ],
    },
    "tel-aviv": {
        "label": "תל אביב", "center": (32.0853, 34.7818), "zoom": 13, "lng_min": 34.775,
        "anchors": [
            (32.0809, 34.7806), (32.0900, 34.7835), (32.0990, 34.7865), (32.0760, 34.7835),
            (32.0850, 34.7895), (32.0950, 34.7925), (32.1080, 34.7985), (32.0720, 34.7815),
            (32.0690, 34.7905), (32.1030, 34.7905), (32.0880, 34.7955), (32.0800, 34.7885),
        ],
    },
    "jerusalem": {
        "label": "ירושלים", "center": (31.7780, 35.2100), "zoom": 12,
        "anchors": [
            (31.7683, 35.2137), (31.7850, 35.2100), (31.7900, 35.2010), (31.7760, 35.2240),
            (31.7620, 35.2120), (31.7810, 35.2200), (31.7950, 35.2240), (31.7700, 35.1960),
            (31.7580, 35.2210), (31.7880, 35.1980), (31.7990, 35.2130), (31.7720, 35.2300),
        ],
    },
    "tiberias": {
        "label": "טבריה", "center": (32.7900, 35.5290), "zoom": 14, "lng_max": 35.532,
        "anchors": [
            (32.7922, 35.5285), (32.7965, 35.5268), (32.7885, 35.5293), (32.7850, 35.5255),
            (32.8000, 35.5275), (32.7805, 35.5268), (32.7765, 35.5290), (32.7925, 35.5250),
            (32.7980, 35.5240), (32.7835, 35.5275), (32.7900, 35.5298), (32.7860, 35.5245),
        ],
    },
}


def _city_point(key: str) -> tuple[float, float]:
    c = CITIES[key]
    lat0, lng0 = random.choice(c["anchors"])
    lat = lat0 + random.uniform(-0.0025, 0.0025)
    lng = lng0 + random.uniform(-0.0025, 0.0025)
    if c.get("lng_min") is not None:
        lng = max(c["lng_min"], lng)
    if c.get("lng_max") is not None:
        lng = min(c["lng_max"], lng)
    return round(lat, 6), round(lng, 6)


def _city_bounds(c: dict) -> list[list[float]]:
    """Padded bounding box around a city's anchors, as [[west, south], [east, north]] (lng/lat) for
    MapLibre maxBounds — so the map can't pan or zoom out past the city."""
    lats = [a[0] for a in c["anchors"]]
    lngs = [a[1] for a in c["anchors"]]
    return [[min(lngs) - 0.025, min(lats) - 0.020], [max(lngs) + 0.025, max(lats) + 0.020]]


@router.get("/cities")
def list_cities():
    """Cities available on the fleet dashboard (center is [lng, lat] for MapLibre)."""
    return [
        {"key": k, "label": c["label"], "center": [c["center"][1], c["center"][0]],
         "zoom": c["zoom"], "bounds": _city_bounds(c)}
        for k, c in CITIES.items()
    ]


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
    keys = [k for k in (body.cities or list(CITIES.keys())) if k in CITIES]
    if not keys:
        raise HTTPException(status_code=400, detail="No valid cities requested")
    db = camera_repo.db

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
        label = CITIES[key]["label"]
        for i in range(1, _city_camera_count(key, body.count) + 1):
            status = random.choice(FLEET_STATUS_POOL)
            street = random.choice(STREETS)
            lat, lng = _city_point(key)
            objs.append(Camera(
                name=f"{label} {i:03d}",
                location=f"{street} {random.randint(1, 120)}, {label}",
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
