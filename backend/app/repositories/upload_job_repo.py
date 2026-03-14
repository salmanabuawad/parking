"""Upload job repository for queue-based processing."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import UploadJob
from app.repositories.base import BaseRepository


class UploadJobRepository(BaseRepository[UploadJob]):
    def __init__(self, db: Session):
        super().__init__(db, UploadJob)

    def get_by_ticket_id(self, ticket_id: int) -> Optional[UploadJob]:
        """Return the job that created this ticket, or None."""
        return self.db.query(UploadJob).filter(UploadJob.ticket_id == ticket_id).first()

    def get_next_queued(self) -> Optional[UploadJob]:
        """Return the oldest queued job with raw_video_path (filesystem), or None."""
        return (
            self.db.query(UploadJob)
            .filter(UploadJob.status == "queued", UploadJob.raw_video_path.isnot(None))
            .order_by(UploadJob.created_at.asc())
            .first()
        )

    def list_queued(self) -> List[UploadJob]:
        return (
            self.db.query(UploadJob)
            .filter(UploadJob.status == "queued")
            .order_by(UploadJob.created_at.asc())
            .all()
        )

    def get_queue_counts(self) -> tuple[int, int]:
        """Return (queued_count, processing_count)."""
        from sqlalchemy import func
        queued = self.db.query(func.count(UploadJob.id)).filter(
            UploadJob.status == "queued", UploadJob.raw_video_path.isnot(None)
        ).scalar() or 0
        processing = self.db.query(func.count(UploadJob.id)).filter(UploadJob.status == "processing").scalar() or 0
        return int(queued), int(processing)

    def get_queue_status(self) -> dict:
        """Return full status: counts (queued, processing, completed, failed) + next queued job IDs."""
        from sqlalchemy import func
        rows = (
            self.db.query(UploadJob.status, func.count(UploadJob.id))
            .group_by(UploadJob.status)
            .all()
        )
        counts = {row[0]: int(row[1]) for row in rows}
        next_ids = [
            r[0]
            for r in self.db.query(UploadJob.id)
            .filter(UploadJob.status == "queued", UploadJob.raw_video_path.isnot(None))
            .order_by(UploadJob.created_at.asc())
            .limit(10)
        ]
        return {
            "queued": counts.get("queued", 0),
            "processing": counts.get("processing", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "next_ids": next_ids,
        }

    def list_recent(self, limit: int = 20) -> List[UploadJob]:
        """Return most recent jobs (all statuses), newest first."""
        return (
            self.db.query(UploadJob)
            .order_by(UploadJob.created_at.desc())
            .limit(limit)
            .all()
        )

    def reset_stuck_processing(self, stuck_minutes: int = 5) -> int:
        """Reset jobs stuck in 'processing' for > stuck_minutes (e.g. worker crashed). Prevents resetting jobs actively being processed."""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import update, and_, or_
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stuck_minutes)
        result = self.db.execute(
            update(UploadJob)
            .where(
                UploadJob.status == "processing",
                UploadJob.raw_video_path.isnot(None),
                or_(UploadJob.processing_started_at.is_(None), UploadJob.processing_started_at < cutoff),
            )
            .values(status="queued", error_message=None, processing_started_at=None)
        )
        self.db.commit()
        return result.rowcount
