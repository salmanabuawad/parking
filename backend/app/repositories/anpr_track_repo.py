"""Persist multi-track ANPR outcomes."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AnprTrackResult


class AnprTrackRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_for_ticket(self, ticket_id: int, tracks: list[dict]) -> None:
        """Replace all rows for a ticket with new ANPR track payloads."""
        self.db.query(AnprTrackResult).filter(AnprTrackResult.ticket_id == ticket_id).delete()
        for t in tracks:
            self.db.add(
                AnprTrackResult(
                    ticket_id=ticket_id,
                    track_id=int(t["track_id"]),
                    raw_digits=str(t.get("raw_digits", ""))[:16],
                    normalized_plate=str(t.get("normalized_plate", ""))[:32],
                    vote_count=int(t.get("vote_count", 1)),
                )
            )
        self.db.commit()

    def list_recent(self, limit: int = 50) -> list[AnprTrackResult]:
        return (
            self.db.query(AnprTrackResult)
            .order_by(AnprTrackResult.created_at.desc())
            .limit(limit)
            .all()
        )
