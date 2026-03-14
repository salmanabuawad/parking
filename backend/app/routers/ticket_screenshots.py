from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Admin, Ticket, TicketScreenshot

router = APIRouter(prefix="/tickets", tags=["ticket-screenshots"])

_DATA_URL_RE = re.compile(r"^data:image/(?P<fmt>png|jpeg|jpg|webp);base64,(?P<data>.+)$", re.IGNORECASE)


class TicketScreenshotCreate(BaseModel):
    image_base64: str = Field(..., description="Blurred screenshot as data URL")
    frame_time_seconds: float = Field(..., ge=0)
    video_timestamp: Optional[datetime] = None
    source_video_id: Optional[str] = None
    captured_by_ui: Optional[str] = None


class TicketScreenshotResponse(BaseModel):
    id: int
    ticket_id: int
    storage_path: str
    frame_time_seconds: float
    video_timestamp: Optional[datetime] = None
    source_video_id: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    media_url: str

    class Config:
        from_attributes = True


def _screenshots_root() -> Path:
    root = settings.videos_dir / "screenshots"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _detect_image_format(raw: bytes) -> str | None:
    """Detect image format from magic bytes (replacement for imghdr, removed in Python 3.13)."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if raw.startswith(b"RIFF") and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return "webp"
    return None


def _decode_image(data_url: str) -> tuple[bytes, str]:
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        raise HTTPException(status_code=400, detail="image_base64 must be a valid image data URL")

    encoded = match.group("data")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not decode screenshot payload") from exc

    if not raw:
        raise HTTPException(status_code=400, detail="Screenshot payload is empty")

    detected = _detect_image_format(raw)
    ext = {
        "jpeg": ".jpg",
        "png": ".png",
        "webp": ".webp",
    }.get(detected or match.group("fmt").lower(), ".png")
    return raw, ext


@router.post("/{ticket_id}/screenshots", response_model=TicketScreenshotResponse)
def create_ticket_screenshot(
    ticket_id: int,
    payload: TicketScreenshotCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    image_bytes, ext = _decode_image(payload.image_base64)
    ticket_dir = _screenshots_root() / f"ticket_{ticket_id}"
    ticket_dir.mkdir(parents=True, exist_ok=True)

    ts = payload.video_timestamp or ticket.captured_at or datetime.now(timezone.utc)
    safe_stamp = ts.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") if ts.tzinfo else ts.strftime("%Y%m%dT%H%M%S")
    filename = f"shot_{safe_stamp}_{int(payload.frame_time_seconds * 1000):09d}{ext}"
    file_path = ticket_dir / filename
    file_path.write_bytes(image_bytes)

    rel_path = str(file_path.relative_to(settings.videos_dir)).replace("\\", "/")
    record = TicketScreenshot(
        ticket_id=ticket_id,
        storage_path=rel_path,
        frame_time_seconds=payload.frame_time_seconds,
        video_timestamp=payload.video_timestamp,
        source_video_id=payload.source_video_id,
        created_by=getattr(admin, "username", None),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return TicketScreenshotResponse(
        id=record.id,
        ticket_id=record.ticket_id,
        storage_path=record.storage_path,
        frame_time_seconds=record.frame_time_seconds,
        video_timestamp=record.video_timestamp,
        source_video_id=record.source_video_id,
        created_at=record.created_at,
        created_by=record.created_by,
        media_url=f"/api/tickets/{ticket_id}/screenshots/{record.id}/image",
    )


@router.get("/{ticket_id}/screenshots", response_model=list[TicketScreenshotResponse])
def list_ticket_screenshots(
    ticket_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    rows = (
        db.query(TicketScreenshot)
        .filter(TicketScreenshot.ticket_id == ticket_id)
        .order_by(TicketScreenshot.created_at.desc(), TicketScreenshot.id.desc())
        .all()
    )
    return [
        TicketScreenshotResponse(
            id=row.id,
            ticket_id=row.ticket_id,
            storage_path=row.storage_path,
            frame_time_seconds=row.frame_time_seconds,
            video_timestamp=row.video_timestamp,
            source_video_id=row.source_video_id,
            created_at=row.created_at,
            created_by=row.created_by,
            media_url=f"/api/tickets/{ticket_id}/screenshots/{row.id}/image",
        )
        for row in rows
    ]


@router.get("/{ticket_id}/screenshots/{screenshot_id}/image")
def get_ticket_screenshot_image(
    ticket_id: int,
    screenshot_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_user),
):
    from fastapi.responses import FileResponse

    row = (
        db.query(TicketScreenshot)
        .filter(TicketScreenshot.id == screenshot_id, TicketScreenshot.ticket_id == ticket_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    file_path = settings.videos_dir / row.storage_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file not found")
    return FileResponse(file_path)


@router.delete("/{ticket_id}/screenshots/{screenshot_id}")
def delete_ticket_screenshot(
    ticket_id: int,
    screenshot_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_user),
):
    row = (
        db.query(TicketScreenshot)
        .filter(TicketScreenshot.id == screenshot_id, TicketScreenshot.ticket_id == ticket_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    file_path = settings.videos_dir / row.storage_path
    if file_path.exists():
        file_path.unlink()

    db.delete(row)
    db.commit()
    return {"ok": True, "message": "Screenshot deleted"}
