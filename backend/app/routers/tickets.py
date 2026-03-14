from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response

from app.database import get_db
from app.dependencies import get_camera_video_repo, get_ticket_repo, get_upload_job_repo
from app.models import AppConfig
from app.repositories import CameraVideoRepository, TicketRepository, UploadJobRepository
from app.services.video_processor import process_video

try:
    from app.config import settings
except Exception:
    class _FallbackSettings:
        videos_dir = Path("videos")
    settings = _FallbackSettings()

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _is_processed_path(video_path: Optional[str]) -> bool:
    if not video_path:
        return False
    p = str(video_path).replace("\\", "/").lower()
    return p.startswith("processed/") or "/processed/" in f"/{p}" or "_processed" in p


def _normalize_blur_kernel_size(value: Optional[int]) -> int:
    k = int(value or 15)
    if k < 3:
        k = 15
    if k % 2 == 0:
        k += 1
    return k


def _get_blur_kernel_size(db) -> int:
    cfg = db.query(AppConfig).first()
    if not cfg:
        return 15
    return _normalize_blur_kernel_size(getattr(cfg, "blur_kernel_size", 15))


def _read_upload_job_raw_video_bytes(ticket, upload_job_repo: Optional[UploadJobRepository]) -> Optional[bytes]:
    if not upload_job_repo:
        return None

    upload_job_id = getattr(ticket, "upload_job_id", None)
    if not upload_job_id:
        return None

    try:
        job = upload_job_repo.get(upload_job_id)
    except Exception:
        return None

    if not job:
        return None

    raw_path = (
        getattr(job, "raw_video_path", None)
        or getattr(job, "video_path", None)
        or getattr(job, "file_path", None)
    )
    if not raw_path:
        return None

    fp = Path(settings.videos_dir) / str(raw_path).replace("\\", "/")
    if fp.exists():
        return fp.read_bytes()
    return None


def _build_processed_video_bytes(
    ticket,
    blur_strength: int,
    video_repo: CameraVideoRepository,
    upload_job_repo: Optional[UploadJobRepository],
) -> bytes:
    # 1) explicit processed blob in DB
    processed_video_id = getattr(ticket, "processed_video_id", None)
    if processed_video_id:
        vid = video_repo.get(processed_video_id)
        if vid and getattr(vid, "data", None):
            return bytes(vid.data)

    # 2) upload-job raw file -> process now
    upload_job_bytes = _read_upload_job_raw_video_bytes(ticket, upload_job_repo)
    if upload_job_bytes:
        processed_bytes, _ = process_video(upload_job_bytes, blur_strength=blur_strength)
        return processed_bytes

    # 3) processed filesystem path only if clearly processed
    video_path = getattr(ticket, "video_path", None)
    if _is_processed_path(video_path):
        fp = Path(settings.videos_dir) / str(video_path).replace("\\", "/")
        if fp.exists():
            return fp.read_bytes()

    # 4) raw DB video -> process now
    raw_video_id = getattr(ticket, "video_id", None)
    if raw_video_id:
        raw_vid = video_repo.get(raw_video_id)
        if raw_vid and getattr(raw_vid, "data", None):
            processed_bytes, _ = process_video(bytes(raw_vid.data), blur_strength=blur_strength)
            return processed_bytes

    raise HTTPException(status_code=404, detail="No source video available for processing")


@router.get("/{ticket_id}/video")
def get_ticket_video(
    ticket_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    upload_job_repo: Optional[UploadJobRepository] = Depends(get_upload_job_repo),
):
    """Processed review video only."""
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    blur = _get_blur_kernel_size(db)
    try:
        data = _build_processed_video_bytes(
            ticket,
            blur_strength=blur,
            video_repo=video_repo,
            upload_job_repo=upload_job_repo,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Processed video build failed for ticket %s", ticket_id)
        raise HTTPException(status_code=500, detail=f"Processed video build failed: {exc}")

    return Response(
        content=data,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/{ticket_id}/processed-video")
def get_ticket_processed_video(
    ticket_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    upload_job_repo: Optional[UploadJobRepository] = Depends(get_upload_job_repo),
):
    return get_ticket_video(
        ticket_id=ticket_id,
        db=db,
        ticket_repo=ticket_repo,
        video_repo=video_repo,
        upload_job_repo=upload_job_repo,
    )


@router.get("/{ticket_id}/raw-video")
def get_ticket_raw_video(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    raw_video_id = getattr(ticket, "video_id", None)
    if not raw_video_id:
        raise HTTPException(status_code=404, detail="No raw video attached")

    raw_vid = video_repo.get(raw_video_id)
    if not raw_vid or not getattr(raw_vid, "data", None):
        raise HTTPException(status_code=404, detail="Raw video not found")

    return Response(content=bytes(raw_vid.data), media_type="video/mp4")


@router.post("/{ticket_id}/reprocess-video")
def reprocess_ticket_video(
    ticket_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    raw_video_id = getattr(ticket, "video_id", None)
    if not raw_video_id:
        raise HTTPException(status_code=404, detail="No raw video attached")

    raw_vid = video_repo.get(raw_video_id)
    if not raw_vid or not getattr(raw_vid, "data", None):
        raise HTTPException(status_code=404, detail="Raw video not found")

    blur = _get_blur_kernel_size(db)
    processed_bytes, preview_jpeg = process_video(bytes(raw_vid.data), blur_strength=blur)

    processed_dir = Path(settings.videos_dir) / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    processed_rel_path = f"processed/ticket_{ticket_id}.mp4"
    processed_abs_path = Path(settings.videos_dir) / processed_rel_path
    processed_abs_path.write_bytes(processed_bytes)

    ticket_image_path = None
    if preview_jpeg:
        ticket_image_rel = f"processed/ticket_{ticket_id}.jpg"
        (Path(settings.videos_dir) / ticket_image_rel).write_bytes(preview_jpeg)
        ticket_image_path = ticket_image_rel

    update_fields = {"video_path": processed_rel_path}
    if ticket_image_path:
        update_fields["ticket_image_path"] = ticket_image_path

    try:
        ticket_repo.update(ticket_id, **update_fields)
    except TypeError:
        ticket_repo.update(ticket_id, video_path=processed_rel_path)

    return {"ok": True, "message": "Video reprocessed with blur", "video_path": processed_rel_path}
