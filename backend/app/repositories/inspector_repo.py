"""Repositories for inspectors (פקחים) and camera segments (מקטעים)."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import CameraSegment, Inspector
from app.repositories.base import BaseRepository


class InspectorRepository(BaseRepository[Inspector]):
    def __init__(self, db: Session):
        super().__init__(db, Inspector)

    def get_by_username(self, username: str) -> Optional[Inspector]:
        return self.db.query(Inspector).filter(Inspector.username == username).first()

    def list_active(self) -> List[Inspector]:
        return self.db.query(Inspector).filter(Inspector.is_active.is_(True)).order_by(Inspector.full_name).all()


class CameraSegmentRepository(BaseRepository[CameraSegment]):
    def __init__(self, db: Session):
        super().__init__(db, CameraSegment)

    def list_for_camera(self, camera_id: int) -> List[CameraSegment]:
        return (
            self.db.query(CameraSegment)
            .filter(CameraSegment.camera_id == camera_id)
            .order_by(CameraSegment.display_order, CameraSegment.id)
            .all()
        )
