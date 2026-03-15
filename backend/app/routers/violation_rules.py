"""Violation rules CRUD — admin can list, activate/deactivate, and update rules."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ViolationRule

router = APIRouter(prefix="/violation-rules", tags=["violation-rules"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ViolationRuleResponse(BaseModel):
    id: int
    rule_id: str
    title_he: str
    title_en: str
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    legal_basis_he: Optional[str] = None
    legal_basis_en: Optional[str] = None
    fine_ils: Optional[int] = None
    is_active: bool

    class Config:
        from_attributes = True


class ViolationRuleUpdate(BaseModel):
    title_he: Optional[str] = None
    title_en: Optional[str] = None
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    legal_basis_he: Optional[str] = None
    legal_basis_en: Optional[str] = None
    fine_ils: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[ViolationRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    """List all violation rules (active and inactive)."""
    return db.query(ViolationRule).order_by(ViolationRule.rule_id).all()


@router.patch("/{rule_id}", response_model=ViolationRuleResponse)
def update_rule(rule_id: str, payload: ViolationRuleUpdate, db: Session = Depends(get_db)):
    """Update a violation rule (e.g. toggle is_active, change fine amount)."""
    rule = db.query(ViolationRule).filter(ViolationRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule
