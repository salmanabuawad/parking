from __future__ import annotations

import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Admin, Ticket, TicketScreenshot

router = APIRouter(prefix="/tickets", tags=["ticket_screenshots"])


class ScreenshotCreate(BaseModel):
    image_base64: str
    frame_time_sec: Optional[float] = None
    captured_at: Optional[str] = None


class ScreenshotResponse(BaseModel):
    id: int
    ticket_id: int
    image_url: str
    storage_path: str
    frame_time_sec: Optional[float] = None
    captured_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None


class ScreenshotListItem(ScreenshotResponse):
    pass


def _decode_base64_image(data_url: str) -> tuple[bytes, str]:
    header, payload = data_url.split(",", 1) if "," in data_url else ("", data_url)
    mime_type = "image/png"
    if header.startswith("data:") and ";base64" in header:
        mime_type = header[5:].split(";", 1)[0] or mime_type
    try:
        return base64.b64decode(payload), mime_type
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload") from exc


def _parse_captured_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/{ticket_id}/screenshots", response_model=ScreenshotResponse)
def save_ticket_screenshot(
    ticket_id: int,
    payload: ScreenshotCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_user),
):
    """Save screenshot to backend storage under videos_dir/screenshots/ticket_{id}/."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    image_bytes, mime_type = _decode_base64_image(payload.image_base64)
    extension = mimetypes.guess_extension(mime_type) or ".png"

    base_dir = Path(settings.videos_dir) / "screenshots" / f"ticket_{ticket_id}"
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"shot_{timestamp}{extension}"
    file_path = base_dir / filename
    file_path.write_bytes(image_bytes)

    stored_rel = str(Path("screenshots") / f"ticket_{ticket_id}" / filename)
    screenshot = TicketScreenshot(
        ticket_id=ticket_id,
        storage_path=stored_rel.replace("\\", "/"),
        frame_time_sec=payload.frame_time_sec,
        captured_at=_parse_captured_at(payload.captured_at),
        created_by=getattr(admin, "username", None),
    )
    db.add(screenshot)
    db.commit()
    db.refresh(screenshot)

    return ScreenshotResponse(
        id=screenshot.id,
        ticket_id=ticket_id,
        image_url=f"/api/tickets/{ticket_id}/screenshots/{screenshot.id}/image",
        storage_path=screenshot.storage_path,
        frame_time_sec=screenshot.frame_time_sec,
        captured_at=screenshot.captured_at,
        created_at=screenshot.created_at,
        created_by=screenshot.created_by,
    )


@router.get("/{ticket_id}/screenshots", response_model=list[ScreenshotListItem])
def list_ticket_screenshots(
    ticket_id: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_user),
):
    rows = (
        db.query(TicketScreenshot)
        .filter(TicketScreenshot.ticket_id == ticket_id)
        .order_by(TicketScreenshot.created_at.desc(), TicketScreenshot.id.desc())
        .all()
    )
    return [
        ScreenshotListItem(
            id=row.id,
            ticket_id=row.ticket_id,
            image_url=f"/api/tickets/{ticket_id}/screenshots/{row.id}/image",
            storage_path=row.storage_path,
            frame_time_sec=row.frame_time_sec,
            captured_at=row.captured_at,
            created_at=row.created_at,
            created_by=row.created_by,
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
    row = (
        db.query(TicketScreenshot)
        .filter(TicketScreenshot.id == screenshot_id, TicketScreenshot.ticket_id == ticket_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    file_path = Path(settings.videos_dir) / row.storage_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot file missing")
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
    file_path = Path(settings.videos_dir) / row.storage_path
    if file_path.exists():
        file_path.unlink()
    db.delete(row)
    db.commit()
    return {"ok": True}
