from __future__ import annotations

import base64
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Admin, Ticket, TicketScreenshot

logger = logging.getLogger(__name__)

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
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        image_bytes, mime_type = _decode_base64_image(payload.image_base64)
        extension = mimetypes.guess_extension(mime_type) or ".png"

        base_dir = Path(settings.videos_dir) / "screenshots" / f"ticket_{ticket_id}"
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Screenshot dir failed: {e!s}") from e

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"shot_{timestamp}{extension}"
        file_path = base_dir / filename
        try:
            file_path.write_bytes(image_bytes)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Screenshot write failed: {e!s}") from e

        stored_rel = str(Path("screenshots") / f"ticket_{ticket_id}" / filename).replace("\\", "/")
        captured_at = _parse_captured_at(payload.captured_at)
        frame_time_sec = payload.frame_time_sec if payload.frame_time_sec is not None else 0.0
        video_ts_text = (captured_at.isoformat() if captured_at else (payload.captured_at or datetime.utcnow().isoformat()))[:64]
        username = getattr(admin, "username", None)
        now = datetime.now(timezone.utc)
        frame_ms = int(frame_time_sec * 1000)

        # Raw INSERT matching actual DB schema. NOT NULL: ticket_id, storage_path, frame_time_seconds.
        params = {
            "ticket_id": ticket_id,
            "storage_path": stored_rel,
            "frame_time_seconds": frame_time_sec,
            "video_timestamp": captured_at,
            "created_by": username,
            "created_at": now,
            "frame_time_sec": frame_time_sec,
            "captured_at": captured_at,
            "image_path": stored_rel,
            "frame_timestamp_ms": frame_ms,
            "video_timestamp_text": video_ts_text or " ",
            "captured_by_val": username,
        }
        try:
            row = db.execute(
                text(
                    """
                    INSERT INTO ticket_screenshots (
                        ticket_id, storage_path, frame_time_seconds,
                        video_timestamp, created_by, created_at,
                        frame_time_sec, captured_at, image_path, frame_timestamp_ms,
                        video_timestamp_text, captured_by, is_blurred_source
                    ) VALUES (
                        :ticket_id, :storage_path, :frame_time_seconds,
                        :video_timestamp, :created_by, :created_at,
                        :frame_time_sec, :captured_at, :image_path, :frame_timestamp_ms,
                        :video_timestamp_text, :captured_by_val, true
                    )
                    RETURNING id, created_at
                    """
                ),
                params,
            ).fetchone()
        except Exception as insert_err:
            db.rollback()
            err_msg = str(insert_err).lower()
            if "column" in err_msg and "does not exist" in err_msg:
                row = db.execute(
                    text(
                        """
                        INSERT INTO ticket_screenshots (ticket_id, storage_path, frame_time_seconds)
                        VALUES (:ticket_id, :storage_path, :frame_time_seconds)
                        RETURNING id, created_at
                        """
                    ),
                    {
                        "ticket_id": ticket_id,
                        "storage_path": stored_rel,
                        "frame_time_seconds": frame_time_sec,
                    },
                ).fetchone()
            else:
                logger.exception("Screenshot INSERT failed for ticket_id=%s", ticket_id)
                raise HTTPException(
                    status_code=500,
                    detail=f"Screenshot save failed: {type(insert_err).__name__}: {str(insert_err)}",
                ) from insert_err

        db.commit()

        sid = row[0]
        created_at_val = row[1]

        return ScreenshotResponse(
            id=sid,
            ticket_id=ticket_id,
            image_url=f"/api/tickets/{ticket_id}/screenshots/{sid}/image",
            storage_path=stored_rel,
            frame_time_sec=frame_time_sec,
            captured_at=captured_at,
            created_at=created_at_val,
            created_by=username,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Screenshot save failed for ticket_id=%s", ticket_id)
        raise HTTPException(status_code=500, detail=f"Screenshot save failed: {type(e).__name__}: {str(e)}") from e


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
    def _path(row: TicketScreenshot) -> str:
        return row.storage_path or row.image_path or ""

    def _frame_sec(row: TicketScreenshot) -> Optional[float]:
        if row.frame_time_sec is not None:
            return float(row.frame_time_sec)
        if row.frame_timestamp_ms is not None:
            return row.frame_timestamp_ms / 1000.0
        return None

    def _captured_at(row: TicketScreenshot) -> Optional[datetime]:
        if row.captured_at is not None:
            return row.captured_at
        if row.video_timestamp_text:
            return _parse_captured_at(row.video_timestamp_text)
        return row.created_at

    return [
        ScreenshotListItem(
            id=row.id,
            ticket_id=row.ticket_id,
            image_url=f"/api/tickets/{ticket_id}/screenshots/{row.id}/image",
            storage_path=_path(row),
            frame_time_sec=_frame_sec(row),
            captured_at=_captured_at(row),
            created_at=row.created_at,
            created_by=row.captured_by or row.created_by,
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
    path = row.storage_path or row.image_path
    if not path:
        raise HTTPException(status_code=404, detail="Screenshot file path missing")
    path_str = path.replace("\\", "/").lstrip("/")
    base = Path(settings.videos_dir).resolve()
    file_path = (base / path_str).resolve()
    if not file_path.is_relative_to(base) or not file_path.exists():
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
    path = row.storage_path or row.image_path
    if path:
        file_path = Path(settings.videos_dir) / path
        if file_path.exists():
            file_path.unlink()
    db.delete(row)
    db.commit()
    return {"ok": True}
