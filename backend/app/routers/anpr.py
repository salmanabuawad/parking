"""ANPR dashboard API: recent per-track detection rows."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.database import get_db
from app.repositories import AnprTrackRepository

router = APIRouter(prefix="/anpr", tags=["anpr"])


@router.get("/recent")
def list_recent_anpr_tracks(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _user=Depends(get_current_user),
):
    """Recent stable ANPR track rows (for dashboard polling)."""
    repo = AnprTrackRepository(db)
    rows = repo.list_recent(limit=limit)
    return {
        "items": [
            {
                "id": r.id,
                "ticket_id": r.ticket_id,
                "track_id": r.track_id,
                "raw_digits": r.raw_digits,
                "normalized_plate": r.normalized_plate,
                "vote_count": r.vote_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
