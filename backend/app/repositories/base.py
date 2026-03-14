"""Base repository with generic CRUD. All repos extend this."""
from typing import Generic, TypeVar, Type, Optional, List

from sqlalchemy.orm import Session

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic repository for standard CRUD operations."""

    def __init__(self, db: Session, model: Type[ModelT]):
        self.db = db
        self.model = model

    def get(self, id: int) -> Optional[ModelT]:
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, order_by=None) -> List[ModelT]:
        q = self.db.query(self.model)
        if order_by is not None:
            q = q.order_by(*order_by) if isinstance(order_by, tuple) else q.order_by(order_by)
        return q.all()

    def create(self, **kwargs) -> ModelT:
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, id: int, **kwargs) -> Optional[ModelT]:
        obj = self.get(id)
        if not obj:
            return None
        for k, v in kwargs.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: int) -> bool:
        obj = self.get(id)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
