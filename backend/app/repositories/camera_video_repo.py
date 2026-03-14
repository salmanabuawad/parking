"""CameraVideo repository."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import CameraVideo
from app.repositories.base import BaseRepository


class CameraVideoRepository(BaseRepository[CameraVideo]):
    def __init__(self, db: Session):
        super().__init__(db, CameraVideo)

    def get_by_name(self, name: str) -> Optional[CameraVideo]:
        return self.db.query(CameraVideo).filter(CameraVideo.name == name).first()
