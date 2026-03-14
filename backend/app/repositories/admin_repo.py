"""Admin repository."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Admin
from app.repositories.base import BaseRepository


class AdminRepository(BaseRepository[Admin]):
    def __init__(self, db: Session):
        super().__init__(db, Admin)

    def get_by_username(self, username: str) -> Optional[Admin]:
        return self.db.query(Admin).filter(Admin.username == username).first()
