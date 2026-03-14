"""Tickets: list, get, approve, reject, update (admin only)."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.auth import get_current_user, get_current_user_for_media
from app.config import settings
from app.dependencies import get_ticket_repo, get_camera_video_repo, get_upload_job_repo
from app.models import Admin, Ticket
from app.repositories import TicketRepository, CameraVideoRepository, UploadJobRepository

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketResponse(BaseModel):
    id: int
    license_plate: str
    plate_detection_reason: Optional[str] = None
    camera_id: Optional[str] = None
    location: Optional[str] = None
    violation_zone: Optional[str] = None
    description: Optional[str] = None
    admin_notes: Optional[str] = None
    fine_amount: Optional[int] = None
    status: str
    video_id: Optional[int] = None
    processed_video_id: Optional[int] = None
    ticket_image_id: Optional[int] = None
    video_path: Optional[str] = None
    ticket_image_path: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    captured_at: Optional[datetime] = None
    video_params: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TicketUpdate(BaseModel):
    license_plate: Optional[str] = None
    location: Optional[str] = None
    violation_zone: Optional[str] = None
    description: Optional[str] = None
    admin_notes: Optional[str] = None
    fine_amount: Optional[int] = None
    status: Optional[str] = None


@router.get("", response_model=List[TicketResponse])
def list_tickets(
    status_filter: Optional[str] = None,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    admin: Admin = Depends(get_current_user),
):
    from app.models import Ticket
    return ticket_repo.get_all(status_filter=status_filter, order_by=(Ticket.created_at.desc(),))


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    admin: Admin = Depends(get_current_user),
):
    t = ticket_repo.get(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    data: TicketUpdate,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    admin: Admin = Depends(get_current_user),
):
    t = ticket_repo.get(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    upd = data.model_dump(exclude_unset=True)
    if data.status and data.status in ("approved", "rejected"):
        upd["reviewed_at"] = datetime.utcnow()
    return ticket_repo.update(ticket_id, **upd)


_ticket_video_cache: dict[int, bytes] = {}


def _build_processed_video_bytes(ticket: Ticket, video_repo: CameraVideoRepository) -> bytes:
    if ticket.video_path:
      fp = Path(settings.videos_dir) / ticket.video_path
      if fp.exists():
          return fp.read_bytes()

    if ticket.processed_video_id:
        vid = video_repo.get(ticket.processed_video_id)
        if vid and vid.data:
            return bytes(vid.data)

    raw_vid_id = ticket.video_id
    if not raw_vid_id:
        raise HTTPException(status_code=404, detail="No video attached to ticket")
    raw_vid = video_repo.get(raw_vid_id)
    if not raw_vid or not raw_vid.data:
        raise HTTPException(status_code=404, detail="Video not found")

    from app.services.video_processor import process_video
    processed_bytes, _ = process_video(bytes(raw_vid.data))
    return processed_bytes


@router.get("/{ticket_id}/video")
def get_ticket_video(
    ticket_id: int,
    request: Request,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    admin: Admin = Depends(get_current_user_for_media),
):
    t = ticket_repo.get(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    refresh = request.query_params.get("refresh") == "1"
    if refresh:
        _ticket_video_cache.pop(ticket_id, None)

    if ticket_id not in _ticket_video_cache:
        try:
            _ticket_video_cache[ticket_id] = _build_processed_video_bytes(t, video_repo)
        except Exception as exc:
            logging.exception("Video processing failed")
            raise HTTPException(status_code=500, detail=f"Video processing failed: {str(exc)}")

    data = _ticket_video_cache[ticket_id]
    total = len(data)
    range_header = request.headers.get("range")
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache", "Accept-Ranges": "bytes"}
    if range_header and range_header.startswith("bytes="):
        try:
            parts = range_header.replace("bytes=", "").split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else total - 1
            end = min(end, total - 1)
            data = data[start : end + 1]
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"
            return Response(content=data, status_code=206, media_type="video/mp4", headers=headers)
        except (ValueError, IndexError):
            pass
    headers["Content-Length"] = str(total)
    return Response(content=data, media_type="video/mp4", headers=headers)


@router.get("/{ticket_id}/processed-video")
def get_ticket_processed_video(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    admin: Admin = Depends(get_current_user_for_media),
):
    t = ticket_repo.get(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        return Response(content=_build_processed_video_bytes(t, video_repo), media_type="video/mp4")
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Processed video load failed")
        raise HTTPException(status_code=500, detail=f"Processed video load failed: {str(exc)}")


@router.get("/{ticket_id}/raw-video")
def get_ticket_raw_video(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    admin: Admin = Depends(get_current_user_for_media),
):
    t = ticket_repo.get(ticket_id)
    if not t or not t.video_id:
        raise HTTPException(status_code=404, detail="Raw video not found")
    vid = video_repo.get(t.video_id)
    if not vid or not vid.data:
        raise HTTPException(status_code=404, detail="Raw video not found")
    return Response(content=vid.data, media_type=vid.content_type or "video/mp4")


@router.post("/{ticket_id}/reprocess-video")
def reprocess_ticket_video(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    upload_job_repo: UploadJobRepository = Depends(get_upload_job_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    admin: Admin = Depends(get_current_user),
):
    from app.services.video_processor import process_video

    t = ticket_repo.get(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not t.video_path and not t.video_id:
        raise HTTPException(status_code=404, detail="No video attached to ticket")

    videos_dir = Path(settings.videos_dir)
    job = upload_job_repo.get_by_ticket_id(ticket_id)
    if job and job.raw_video_path:
        raw_path = (videos_dir / job.raw_video_path.strip().replace("\\", "/")).resolve()
        if not raw_path.exists():
            raise HTTPException(status_code=404, detail="Raw video file not found")
        video_bytes = raw_path.read_bytes()
    elif t.video_id:
        raw_vid = video_repo.get(t.video_id)
        if not raw_vid or not raw_vid.data:
            raise HTTPException(status_code=404, detail="Video not found in database")
        video_bytes = bytes(raw_vid.data)
    else:
        raise HTTPException(status_code=404, detail="No source video for reprocessing")

    processed_bytes, ticket_jpeg = process_video(video_bytes)
    video_path = t.video_path or f"processed/ticket_{ticket_id}.mp4"
    ticket_image_path = t.ticket_image_path or f"frames/ticket_{ticket_id}.jpg"
    proc_path = videos_dir / video_path
    proc_path.parent.mkdir(parents=True, exist_ok=True)
    proc_path.write_bytes(processed_bytes)
    frame_path = videos_dir / ticket_image_path
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    frame_path.write_bytes(ticket_jpeg)
    if not t.video_path or not t.ticket_image_path:
        ticket_repo.update(ticket_id, video_path=video_path, ticket_image_path=ticket_image_path)
    _ticket_video_cache.pop(ticket_id, None)
    return {"ok": True, "message": "Video reprocessed with blur"}


@router.get("/{ticket_id}/image")
def get_ticket_image(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    admin: Admin = Depends(get_current_user),
):
    t = ticket_repo.get(ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if t.ticket_image_path:
        fp = Path(settings.videos_dir) / t.ticket_image_path
        if fp.exists():
            return FileResponse(fp, media_type="image/jpeg")
    if not t.ticket_image_id:
        raise HTTPException(status_code=404, detail="No ticket image yet")
    img = video_repo.get(t.ticket_image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=img.data, media_type=img.content_type or "image/jpeg")
