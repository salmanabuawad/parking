"""Mobile upload: video + GPS + time. Store in filesystem, return ACK, process in background."""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form

logger = logging.getLogger(__name__)

from app.config import settings
from app.dependencies import get_upload_job_repo
from app.repositories import UploadJobRepository

router = APIRouter(prefix="/upload", tags=["upload"])


def _parse_captured_at(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


@router.post("/violation")
async def upload_violation(
    video: UploadFile,
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    captured_at: str = Form(...),
    license_plate: str = Form("11111"),
    violation_zone: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    submitted_by: Optional[str] = Form(None),
    job_repo: UploadJobRepository = Depends(get_upload_job_repo),
):
    """
    Upload violation video from mobile. Saves to videos/raw/, returns ACK immediately.
    Poll GET /upload/job/{job_id} for status; when completed, ticket_id is returned.
    """
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    captured_dt = _parse_captured_at(captured_at)

    data = await video.read()
    if not data:
        raise HTTPException(status_code=400, detail="Video file is empty")

    # Save to filesystem: videos/raw/{uuid}.mp4 (use resolved path so worker finds it)
    raw_dir = (settings.videos_dir / "raw").resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    ext = ".mp4" if "mp4" in (video.content_type or "") else ".video"
    fname = f"{uuid.uuid4().hex}{ext}"
    raw_path = raw_dir / fname
    raw_path.write_bytes(data)
    if not raw_path.exists():
        raise HTTPException(status_code=500, detail="Failed to save video file to disk")
    logger.info("Upload saved to %s (videos_dir=%s)", raw_path, settings.videos_dir.resolve())
    rel_path = f"raw/{fname}"

    lat = latitude if latitude is not None else 0.0
    lng = longitude if longitude is not None else 0.0
    job = job_repo.create(
        raw_video_path=rel_path,
        status="queued",
        latitude=lat,
        longitude=lng,
        captured_at=captured_dt,
        license_plate=license_plate,
        violation_zone=violation_zone or "red_white",
        description=description or f"Mobile upload at {lat:.6f}, {lng:.6f}",
        submitted_by=submitted_by,
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Upload received. Video will be processed in the background. Poll /upload/job/{job_id} for status.",
    }


@router.get("/jobs")
def list_jobs(
    limit: int = 50,
    job_repo: UploadJobRepository = Depends(get_upload_job_repo),
):
    """List recent upload jobs (newest first). Includes source, target for maintenance."""
    jobs = job_repo.list_recent(limit=limit)
    return [
        {
            "job_id": j.id,
            "status": j.status,
            "ticket_id": j.ticket_id,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "license_plate": j.license_plate,
            "source": j.raw_video_path,
            "target": f"processed/job_{j.id}.mp4" if j.ticket_id else None,
        }
        for j in jobs
    ]


@router.post("/reset-stuck-jobs")
def reset_stuck_jobs(
    stuck_minutes: int = 5,
    job_repo: UploadJobRepository = Depends(get_upload_job_repo),
):
    """Reset jobs stuck in 'processing' (worker crashed) back to queued. Use stuck_minutes=0 for immediate reset."""
    count = job_repo.reset_stuck_processing(stuck_minutes=stuck_minutes)
    return {"reset_count": count, "message": f"Reset {count} stuck job(s) to queued"}


@router.post("/job/{job_id}/rerun")
def rerun_job(
    job_id: int,
    job_repo: UploadJobRepository = Depends(get_upload_job_repo),
):
    """Reset job to queued so worker reprocesses it. Works for failed/completed jobs."""
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.raw_video_path:
        raise HTTPException(status_code=400, detail="Job has no raw video path")
    job_repo.update(job_id, status="queued", error_message=None, ticket_id=None)
    return {"job_id": job_id, "status": "queued", "message": "Job requeued for processing"}


@router.get("/job/{job_id}")
def get_job_status(
    job_id: int,
    job_repo: UploadJobRepository = Depends(get_upload_job_repo),
):
    """Poll job status. When completed, ticket_id is set. When failed, error_message is set."""
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "ticket_id": job.ticket_id,
        "error_message": job.error_message,
    }
