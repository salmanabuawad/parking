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


# ── Sample fleet generator (dashboard demo data) ──────────────────────────────
NETANYA_STREETS = [
    "הרצל", "ויצמן", "שדרות ניצה", "דיזנגוף", "רזיאל", "בן גוריון", "סמילנסקי",
    "רמז", "אוסטרובסקי", "המעפילים", "גד מכנס", "פינסקר", "שער העמק", "בני בנימין",
]
# On-land anchor points across Netanya neighborhoods (lat, lng). Cameras scatter around these with a
# small jitter so none fall in the sea (the coast is ~34.852; a blind west-reaching box put pins in
# the water) or in empty fields. All anchors are lng ≥ 34.858, safely inland.
NETANYA_ANCHORS = [
    (32.3286, 34.8590), (32.3240, 34.8615), (32.3320, 34.8600), (32.3340, 34.8635),
    (32.3190, 34.8600), (32.3155, 34.8640), (32.3110, 34.8615), (32.3070, 34.8648),
    (32.3040, 34.8605), (32.3270, 34.8648), (32.3210, 34.8662), (32.3140, 34.8632),
    (32.3225, 34.8585), (32.3300, 34.8660),
]
# Weighted status pool: ~70% online, 15% offline, 10% maintenance, 5% error
FLEET_STATUS_POOL = (["online"] * 70) + (["offline"] * 15) + (["maintenance"] * 10) + (["error"] * 5)


def _netanya_point() -> tuple[float, float]:
    lat0, lng0 = random.choice(NETANYA_ANCHORS)
    lat = lat0 + random.uniform(-0.0035, 0.0035)
    lng = max(34.855, lng0 + random.uniform(-0.0035, 0.0035))  # clamp: never west into the sea
    return round(lat, 6), round(lng, 6)


class FleetRequest(BaseModel):
    count: int = 100
    clear: bool = True   # remove previously generated demo cameras first


@router.post("/generate-fleet")
def generate_fleet(
    body: FleetRequest | None = None,
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Generate N demo cameras spread across Netanya with varied operational status, for the fleet
    dashboard. Generated cameras are tagged connection_config.generated=true; re-running with
    clear=true removes the previous batch so it doesn't accumulate."""
    body = body or FleetRequest()
    n = max(1, min(2000, body.count))
    db = camera_repo.db

    removed = 0
    if body.clear:
        existing = [c for c in db.query(Camera).all() if (c.connection_config or {}).get("generated")]
        for c in existing:
            db.delete(c)
            removed += 1
        if existing:
            db.commit()

    objs = []
    for i in range(1, n + 1):
        status = random.choice(FLEET_STATUS_POOL)
        street = random.choice(NETANYA_STREETS)
        lat, lng = _netanya_point()
        objs.append(Camera(
            name=f"מצלמה {i:03d}",
            location=f"{street} {random.randint(1, 120)}, נתניה",
            connection_type="ip",
            connection_config={"generated": True},
            source_type="uploaded_image",
            is_active=(status != "offline"),
            status=status,
            latitude=lat,
            longitude=lng,
        ))
    db.add_all(objs)
    db.commit()
    return {"created": len(objs), "removed": removed, "by_status": dict(Counter(o.status for o in objs))}
