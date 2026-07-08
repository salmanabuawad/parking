"""Camera CRUD API. Cameras can connect via IP, Bluetooth, WiFi, RTSP, USB, etc."""
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import settings
from app.auth import get_current_user
from app.dependencies import get_camera_repo, get_camera_video_repo
from app.repositories import CameraRepository, CameraVideoRepository
from app.schemas import CameraCreate, CameraUpdate, CameraResponse
from app.services.video_processor import process_video

router = APIRouter(prefix="/cameras", tags=["cameras"])

# Cache blurred videos by video_id (processed on first request)
_blurred_cache: Dict[int, bytes] = {}


@router.get("", response_model=List[CameraResponse])
def list_cameras(
    active_only: bool = False,
    camera_repo: CameraRepository = Depends(get_camera_repo),
    _=Depends(get_current_user),
):
    """List all cameras. Use ?active_only=true to filter active only."""
    return camera_repo.get_all(active_only=active_only)


@router.get("/{camera_id}/video")
def get_camera_video(
    camera_id: int,
    refresh: bool = False,
    camera_repo: CameraRepository = Depends(get_camera_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    _=Depends(get_current_user),
):
    """Stream blurred video from DB for this camera. Use ?refresh=1 to force reprocess."""
    global _blurred_cache
    cam = camera_repo.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    video_id = (cam.connection_config or {}).get("video_id")
    if not video_id:
        raise HTTPException(status_code=404, detail="No video attached to this camera")
    vid = video_repo.get(video_id)
    if not vid:
        raise HTTPException(status_code=404, detail="Video not found")
    if refresh and video_id in _blurred_cache:
        del _blurred_cache[video_id]
    if video_id not in _blurred_cache:
        blurred, _ = process_video(vid.data)
        _blurred_cache[video_id] = blurred
    return Response(
        content=_blurred_cache[video_id],
        media_type=vid.content_type or "video/mp4",
        headers={"Cache-Control": "no-store, no-cache"},
    )


@router.get("/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: int, camera_repo: CameraRepository = Depends(get_camera_repo), _=Depends(get_current_user)):
    """Return the camera's calibration snapshot JPEG (saved frame; else a live RTSP grab)."""
    cam = camera_repo.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    if cam.snapshot_path:
        p = Path(settings.videos_dir) / cam.snapshot_path
        if p.exists():
            return Response(content=p.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    if cam.source_type == "rtsp" and cam.rtsp_url:
        from app.services.camera_snapshot import grab_rtsp_frame
        got = grab_rtsp_frame(cam.rtsp_url)
        if got:
            return Response(content=got[0], media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    if cam.source_type == "simulation":
        from app.services import simulation as sim
        src = (cam.connection_config or {}).get("simulation_source")
        got = sim.frame_for_source(src) if src else None
        if got:
            return Response(content=got[0], media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404, detail="No snapshot — upload an image/video, set an RTSP URL, or use a simulation source")


@router.post("/{camera_id}/snapshot")
async def set_camera_snapshot(
    camera_id: int,
    file: Optional[UploadFile] = File(None),
    camera_repo: CameraRepository = Depends(get_camera_repo),
    _=Depends(get_current_user),
):
    """Set the calibration snapshot from an uploaded image, an uploaded video (one frame extracted),
    or a live RTSP grab (no file). Saves the JPEG + records its pixel resolution."""
    cam = camera_repo.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    from app.services import camera_snapshot as cs
    result = None
    source_type = cam.source_type or "uploaded_image"
    if file is not None:
        content = await file.read()
        name = (file.filename or "").lower()
        is_video = (file.content_type or "").lower().startswith("video/") or name.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm"))
        if is_video:
            result = cs.frame_from_video_bytes(content)
            source_type = "uploaded_video"
        else:
            result = cs.normalize_image_bytes(content)
            source_type = "uploaded_image"
    elif cam.source_type == "simulation" and (cam.connection_config or {}).get("simulation_source"):
        from app.services import simulation as sim
        result = sim.frame_for_source((cam.connection_config or {}).get("simulation_source"))
        source_type = "simulation"
    elif cam.rtsp_url:
        result = cs.grab_rtsp_frame(cam.rtsp_url)
        source_type = "rtsp"

    if not result:
        raise HTTPException(status_code=400, detail="Could not obtain a frame (bad file or unreachable RTSP)")

    jpeg, w, h = result
    rel = f"camera_snapshots/camera_{camera_id}.jpg"
    dest = Path(settings.videos_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(jpeg)
    # Keep the existing calibration if polygon sections already exist at a different resolution, so
    # they stay valid (the UI warns about the mismatch); otherwise (re)calibrate to this snapshot.
    from app.models import CameraSegment
    has_sections = camera_repo.db.query(CameraSegment).filter(CameraSegment.camera_id == camera_id).count() > 0
    keep = bool(has_sections and cam.calibration_width and (cam.calibration_width != w or cam.calibration_height != h))
    fields = {"snapshot_path": rel, "source_type": source_type}
    if not keep:
        fields["calibration_width"] = w
        fields["calibration_height"] = h
    camera_repo.update(camera_id, **fields)
    return {"snapshot_path": rel, "width": w, "height": h, "source_type": source_type,
            "calibration_width": cam.calibration_width if keep else w,
            "calibration_height": cam.calibration_height if keep else h}


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: int, camera_repo: CameraRepository = Depends(get_camera_repo), _=Depends(get_current_user)):
    """Get a camera by ID."""
    cam = camera_repo.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.post("", response_model=CameraResponse, status_code=201)
def create_camera(
    data: CameraCreate,
    camera_repo: CameraRepository = Depends(get_camera_repo),
    _=Depends(get_current_user),
):
    """Add a new camera. Connection config examples:
    - IP: {"ip": "192.168.1.100", "port": 554}
    - WiFi: {"ssid": "MyRouter", "password": "..."}
    - Bluetooth: {"address": "AA:BB:CC:DD:EE:FF"}
    - RTSP: {"url": "rtsp://192.168.1.100:554/stream"}
    Params can be manual or from manufacturer manual, e.g.:
    {"moving": true, "night_light": true, "resolution": "1080p", "fps": 30}
    """
    return camera_repo.create(**data.model_dump())


class ZoneGridIn(BaseModel):
    cols: int
    rows: int
    # "c,r" -> list of violation rule_ids painted on that cell (0/1/many). Sparse (only painted cells).
    cells: dict[str, list[str]] = {}


@router.put("/{camera_id}/zone-grid", response_model=CameraResponse)
def set_zone_grid(
    camera_id: int,
    payload: ZoneGridIn,
    camera_repo: CameraRepository = Depends(get_camera_repo),
    _=Depends(get_current_user),
):
    """Save the grid zone-map — image cells painted with violation types. Stored as
    {cols, rows, cells:{"c,r": [rule_id, ...]}}; a car's position maps to a cell → its violation
    type(s). A cell may carry several types. Empty cells are dropped and ids de-duped so the map
    stays sparse."""
    cam = camera_repo.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    cols = max(1, min(200, int(payload.cols)))
    rows = max(1, min(200, int(payload.rows)))
    cells: dict[str, list[str]] = {}
    for key, ids in (payload.cells or {}).items():
        deduped = list(dict.fromkeys(rid for rid in (ids or []) if rid))
        if deduped:
            cells[key] = deduped
    return camera_repo.update(camera_id, zone_grid={"cols": cols, "rows": rows, "cells": cells})


@router.patch("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: int,
    data: CameraUpdate,
    camera_repo: CameraRepository = Depends(get_camera_repo),
    _=Depends(get_current_user),
):
    """Update camera config."""
    cam = camera_repo.update(camera_id, **data.model_dump(exclude_unset=True))
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: int, camera_repo: CameraRepository = Depends(get_camera_repo), _=Depends(get_current_user)):
    """Remove a camera."""
    if not camera_repo.delete(camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")
    return None
