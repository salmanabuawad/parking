"""Field configuration endpoints — control column width, order, visibility per grid."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db
from ..auth import get_current_user as require_admin
from ..schemas import FieldConfigurationUpsert, FieldConfigurationResponse, FieldConfigurationBulkUpsert
from ..models import FieldConfiguration

router = APIRouter(prefix="/field-configurations", tags=["field-configurations"])


@router.get("", response_model=list[FieldConfigurationResponse])
def list_field_configurations(
    grid_name: str | None = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    q = db.query(FieldConfiguration)
    if grid_name:
        q = q.filter(FieldConfiguration.grid_name == grid_name)
    return q.order_by(FieldConfiguration.grid_name, FieldConfiguration.column_order, FieldConfiguration.field_name).all()


@router.post("/upsert", response_model=FieldConfigurationResponse)
def upsert_field_configuration(
    payload: FieldConfigurationUpsert,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    existing = db.query(FieldConfiguration).filter(
        FieldConfiguration.grid_name == payload.grid_name,
        FieldConfiguration.field_name == payload.field_name,
    ).first()
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing
    obj = FieldConfiguration(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/upsert-bulk")
def upsert_bulk_field_configurations(
    payload: FieldConfigurationBulkUpsert,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    count = 0
    for item in payload.items:
        existing = db.query(FieldConfiguration).filter(
            FieldConfiguration.grid_name == item.grid_name,
            FieldConfiguration.field_name == item.field_name,
        ).first()
        if existing:
            for k, v in item.model_dump().items():
                setattr(existing, k, v)
        else:
            db.add(FieldConfiguration(**item.model_dump()))
        count += 1
    db.commit()
    return {"count": count}


@router.delete("/{grid_name}/{field_name}")
def delete_field_configuration(
    grid_name: str,
    field_name: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    obj = db.query(FieldConfiguration).filter(
        FieldConfiguration.grid_name == grid_name,
        FieldConfiguration.field_name == field_name,
    ).first()
    if obj:
        db.delete(obj)
        db.commit()
    return {"ok": True}
