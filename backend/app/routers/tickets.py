from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
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


def _ticket_dict(t) -> dict:
    return {
        "id": t.id,
        "license_plate": t.license_plate,
        "status": t.status,
        "location": t.location,
        "violation_zone": t.violation_zone,
        "description": t.description,
        "admin_notes": t.admin_notes,
        "fine_amount": t.fine_amount,
        "latitude": t.latitude,
        "longitude": t.longitude,
        "captured_at": t.captured_at.isoformat() if t.captured_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
        "plate_detection_reason": t.plate_detection_reason,
        "violation_rule_id": getattr(t, "violation_rule_id", None),
        "violation_decision": getattr(t, "violation_decision", None),
        "violation_confidence": getattr(t, "violation_confidence", None),
        "violation_description_he": getattr(t, "violation_description_he", None),
        "violation_description_en": getattr(t, "violation_description_en", None),
    }


@router.get("")
def list_tickets(
    status: Optional[str] = None,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
):
    tickets = ticket_repo.list_all()
    if status:
        tickets = [t for t in tickets if t.status == status]
    return [_ticket_dict(t) for t in tickets]


@router.get("/{ticket_id}/detail")
def get_ticket_detail(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_dict(ticket)


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
    processed_video_id = getattr(ticket, "processed_video_id", None)
    if processed_video_id:
        vid = video_repo.get(processed_video_id)
        if vid and getattr(vid, "data", None):
            return bytes(vid.data)

    upload_job_bytes = _read_upload_job_raw_video_bytes(ticket, upload_job_repo)
    if upload_job_bytes:
        processed_bytes, _ = process_video(upload_job_bytes, blur_strength=blur_strength)
        return processed_bytes

    video_path = getattr(ticket, "video_path", None)
    if _is_processed_path(video_path):
        fp = Path(settings.videos_dir) / str(video_path).replace("\\", "/")
        if fp.exists():
            return fp.read_bytes()

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

@router.get("")
def list_tickets(
    status: Optional[str] = None,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    all_tickets = ticket_repo.list_all()
    if status:
        all_tickets = [t for t in all_tickets if t.status == status]
    return [
        {
            "id": t.id,
            "license_plate": t.license_plate,
            "status": t.status,
            "location": t.location,
            "violation_zone": t.violation_zone,
            "captured_at": t.captured_at.isoformat() if t.captured_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "description": t.description,
            "fine_amount": t.fine_amount,
        }
        for t in all_tickets
    ]


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: dict,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
):
    """Update ticket status, fine, admin notes, or license plate. Used for approve/reject/edit."""
    from datetime import datetime, timezone
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    allowed = {"status", "fine_amount", "admin_notes", "license_plate", "description", "violation_zone"}
    update_kw = {k: v for k, v in payload.items() if k in allowed}

    if "status" in update_kw and update_kw["status"] in ("approved", "rejected"):
        update_kw["reviewed_at"] = datetime.now(timezone.utc)

    try:
        ticket_repo.update(ticket_id, **update_kw)
    except TypeError:
        for k, v in update_kw.items():
            setattr(ticket, k, v)
        db.commit()

    ticket = ticket_repo.get(ticket_id)
    return _ticket_dict(ticket)


@router.get("/{ticket_id}/screenshots")
def list_screenshots(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    db=Depends(get_db),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    from sqlalchemy import text as _text
    rows = db.execute(
        _text("SELECT id, storage_path, frame_time_sec, frame_timestamp_ms, created_at FROM ticket_screenshots WHERE ticket_id = :tid ORDER BY id"),
        {"tid": ticket_id},
    ).fetchall()

    result = []
    for r in rows:
        frame_sec = r[2] if r[2] is not None else (r[3] / 1000.0 if r[3] is not None else None)
        result.append({
            "id": r[0],
            "storage_path": r[1],
            "frame_time_seconds": frame_sec,
            "created_at": r[4].isoformat() if r[4] else None,
        })
    return result


@router.get("/{ticket_id}/screenshots/{screenshot_id}/image")
def get_screenshot_image(
    ticket_id: int,
    screenshot_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    from sqlalchemy import text as _text
    row = db.execute(
        _text("SELECT storage_path FROM ticket_screenshots WHERE id = :sid AND ticket_id = :tid"),
        {"sid": screenshot_id, "tid": ticket_id},
    ).fetchone()

    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    fp = Path(settings.videos_dir) / str(row[0]).replace("\\", "/")
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Screenshot file missing")

    return Response(content=fp.read_bytes(), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=86400"})
