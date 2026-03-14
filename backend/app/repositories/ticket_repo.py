"""Ticket repository."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Ticket
from app.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, db: Session):
        super().__init__(db, Ticket)

    def get_all(self, status_filter: Optional[str] = None, order_by=None) -> List[Ticket]:
        q = self.db.query(Ticket)
        if status_filter:
            q = q.filter(Ticket.status == status_filter)
        if order_by is not None:
            q = q.order_by(*order_by) if isinstance(order_by, tuple) else q.order_by(order_by)
        return q.all()

    def list_pending(self) -> List[Ticket]:
        return self.get_all(status_filter="pending_review", order_by=Ticket.created_at.desc())

    def list_all(self) -> List[Ticket]:
        return self.get_all(order_by=Ticket.created_at.desc())
