"""Vehicle exemptions / whitelist CRUD (requirement 13). Authenticated (rule 5)."""
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import VehicleExemption

router = APIRouter(prefix="/exemptions", tags=["exemptions"])


class ExemptionBase(BaseModel):
    plate_number: str
    exemption_type: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    is_active: bool = True


class ExemptionCreate(ExemptionBase):
    pass


class ExemptionUpdate(BaseModel):
    plate_number: Optional[str] = None
    exemption_type: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ExemptionResponse(ExemptionBase):
    id: int

    class Config:
        from_attributes = True


@router.get("", response_model=List[ExemptionResponse])
def list_exemptions(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(VehicleExemption).order_by(VehicleExemption.id.desc()).all()


@router.post("", response_model=ExemptionResponse, status_code=status.HTTP_201_CREATED)
def create_exemption(data: ExemptionCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = VehicleExemption(
        plate_number=re.sub(r"\D", "", data.plate_number or ""),
        exemption_type=data.exemption_type,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        notes=data.notes,
        is_active=data.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{exemption_id}", response_model=ExemptionResponse)
def update_exemption(exemption_id: int, data: ExemptionUpdate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(VehicleExemption).filter(VehicleExemption.id == exemption_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Exemption not found")
    fields = data.model_dump(exclude_unset=True)
    if "plate_number" in fields and fields["plate_number"]:
        fields["plate_number"] = re.sub(r"\D", "", fields["plate_number"])
    for k, v in fields.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{exemption_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exemption(exemption_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.query(VehicleExemption).filter(VehicleExemption.id == exemption_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Exemption not found")
    db.delete(row)
    db.commit()
