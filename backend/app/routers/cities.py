"""City / map management — admin-editable cities for the fleet dashboard and camera city dropdowns."""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import City
from app.services.cities import load_cities

router = APIRouter(prefix="/cities", tags=["cities"])


class CityIn(BaseModel):
    label: str
    center_lat: float
    center_lng: float
    zoom: float = 13
    bounds: Optional[list] = None      # [[west, south], [east, north]]
    is_active: bool = True


class ReorderIn(BaseModel):
    order: list[int]                   # city ids in the desired display order


def _slugify(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (label or "").strip().lower()).strip("-")
    return s or "city"


def _unique_key(db: Session, base: str) -> str:
    key, i = base, 2
    while db.query(City).filter(City.key == key).first():
        key = f"{base}-{i}"
        i += 1
    return key


def _serialize(c: City) -> dict:
    return {
        "id": c.id,
        "key": c.key,
        "label": c.label,
        "center": [c.center_lng, c.center_lat],   # [lng, lat] for MapLibre
        "center_lat": c.center_lat,
        "center_lng": c.center_lng,
        "zoom": c.zoom,
        "bounds": c.bounds,
        "sort_order": c.sort_order,
        "is_active": c.is_active,
    }


@router.get("")
def list_cities(include_inactive: bool = False, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [_serialize(c) for c in load_cities(db, include_inactive=include_inactive)]


@router.post("")
def create_city(body: CityIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="שם העיר חסר")
    max_order = db.query(func.max(City.sort_order)).scalar()
    c = City(
        key=_unique_key(db, _slugify(label)),
        label=label,
        center_lat=body.center_lat,
        center_lng=body.center_lng,
        zoom=body.zoom,
        bounds=body.bounds,
        is_active=body.is_active,
        sort_order=(max_order + 1) if max_order is not None else 0,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.put("/{city_id}")
def update_city(city_id: int, body: CityIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(City).filter(City.id == city_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="City not found")
    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="שם העיר חסר")
    c.label = label
    c.center_lat = body.center_lat
    c.center_lng = body.center_lng
    c.zoom = body.zoom
    c.bounds = body.bounds
    c.is_active = body.is_active
    db.commit()
    db.refresh(c)
    return _serialize(c)


@router.delete("/{city_id}")
def delete_city(city_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    c = db.query(City).filter(City.id == city_id).first()
    if c:
        db.delete(c)
        db.commit()
    return {"ok": True}


@router.post("/reorder")
def reorder_cities(body: ReorderIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    for i, cid in enumerate(body.order):
        db.query(City).filter(City.id == cid).update({City.sort_order: i})
    db.commit()
    return {"ok": True}
