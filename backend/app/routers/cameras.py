"""Camera CRUD API. Cameras can connect via IP, Bluetooth, WiFi, RTSP, USB, etc."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import Dict, List

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
):
    """List all cameras. Use ?active_only=true to filter active only."""
    return camera_repo.get_all(active_only=active_only)


@router.get("/{camera_id}/video")
def get_camera_video(
    camera_id: int,
    refresh: bool = False,
    camera_repo: CameraRepository = Depends(get_camera_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
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


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: int, camera_repo: CameraRepository = Depends(get_camera_repo)):
    """Get a camera by ID."""
    cam = camera_repo.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.post("", response_model=CameraResponse, status_code=201)
def create_camera(
    data: CameraCreate,
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Add a new camera. Connection config examples:
    - IP: {"ip": "192.168.1.100", "port": 554}
    - WiFi: {"ssid": "MyRouter", "password": "..."}
    - Bluetooth: {"address": "AA:BB:CC:DD:EE:FF"}
    - RTSP: {"url": "rtsp://192.168.1.100:554/stream"}
    Params can be manual or from manufacturer manual, e.g.:
    {"moving": true, "night_light": true, "resolution": "1080p", "fps": 30}
    """
    return camera_repo.create(
        name=data.name,
        location=data.location,
        connection_type=data.connection_type,
        connection_config=data.connection_config,
        param_source=data.param_source,
        params=data.params,
        manufacturer=data.manufacturer,
        model=data.model,
        is_active=data.is_active,
    )


@router.patch("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: int,
    data: CameraUpdate,
    camera_repo: CameraRepository = Depends(get_camera_repo),
):
    """Update camera config."""
    cam = camera_repo.update(camera_id, **data.model_dump(exclude_unset=True))
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: int, camera_repo: CameraRepository = Depends(get_camera_repo)):
    """Remove a camera."""
    if not camera_repo.delete(camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")
    return None
