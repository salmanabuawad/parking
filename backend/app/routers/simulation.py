"""Simulation API — use bundled sample clips as stand-in cameras so the whole camera-zone
configuration flow can be exercised without live RTSP hardware.

``POST /simulation/cameras`` seeds one camera per clip (extracting a calibration snapshot from the
clip); the zone configurator then draws enforcement sections on that snapshot exactly as it would for
a real camera. Idempotent by ``simulation_source`` — re-running refreshes the snapshot, not creates
duplicates. A simulation camera can re-grab a fresh (random) frame via the normal snapshot endpoint.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_camera_repo
from app.repositories import CameraRepository
from app.services import simulation as sim

router = APIRouter(prefix="/simulation", tags=["simulation"])


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
    for name in names:
        got = sim.frame_for_source(name, seek_frac=body.seek_frac)
        if not got:
            continue
        jpeg, w, h = got
        cam = _existing_sim_camera(camera_repo, name)
        if cam is None:
            cam = camera_repo.create(
                name=f"סימולציה {name.upper()}",
                location="סימולציה",
                connection_type="simulation",
                connection_config={"simulation_source": name},
                source_type="simulation",
                is_active=True,
            )
        rel = _save_snapshot(cam.id, jpeg)
        camera_repo.update(
            cam.id,
            snapshot_path=rel,
            calibration_width=w,
            calibration_height=h,
            source_type="simulation",
        )
        out.append({"id": cam.id, "name": cam.name, "source": name, "width": w, "height": h})

    if not out:
        raise HTTPException(status_code=400, detail="לא ניתן לחלץ פריים מאף קליפ סימולציה")
    return {"cameras": out, "count": len(out)}
