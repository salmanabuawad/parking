"""Camera repository."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Camera
from app.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera]):
    def __init__(self, db: Session):
        super().__init__(db, Camera)

    def get_all(self, active_only: bool = False, order_by=None) -> List[Camera]:
        q = self.db.query(Camera)
        if active_only:
            q = q.filter(Camera.is_active == True)
        ob = order_by if order_by is not None else Camera.name
        q = q.order_by(*ob) if isinstance(ob, tuple) else q.order_by(ob)
        return q.all()

    def list_active(self) -> List[Camera]:
        return self.get_all(active_only=True, order_by=Camera.name)

    def list_all(self) -> List[Camera]:
        return self.get_all(order_by=Camera.name)
