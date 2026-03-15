"""Parking zones CRUD + camera zone assignment."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ParkingZone, Camera

router = APIRouter(prefix="/parking-zones", tags=["parking-zones"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ParkingZoneResponse(BaseModel):
    id: int
    zone_code: str
    name_he: str
    name_en: str
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class ParkingZoneCreate(BaseModel):
    zone_code: str
    name_he: str
    name_en: str
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    is_active: bool = True


class ParkingZoneUpdate(BaseModel):
    name_he: Optional[str] = None
    name_en: Optional[str] = None
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[ParkingZoneResponse])
def list_zones(db: Session = Depends(get_db)):
    return db.query(ParkingZone).order_by(ParkingZone.zone_code).all()


@router.post("", response_model=ParkingZoneResponse, status_code=201)
def create_zone(payload: ParkingZoneCreate, db: Session = Depends(get_db)):
    existing = db.query(ParkingZone).filter(ParkingZone.zone_code == payload.zone_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Zone '{payload.zone_code}' already exists")
    zone = ParkingZone(**payload.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.patch("/{zone_id}", response_model=ParkingZoneResponse)
def update_zone(zone_id: int, payload: ParkingZoneUpdate, db: Session = Depends(get_db)):
    zone = db.query(ParkingZone).filter(ParkingZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = db.query(ParkingZone).filter(ParkingZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(zone)
    db.commit()


# --- Camera zone assignment ---

@router.get("/camera/{camera_id}", response_model=List[ParkingZoneResponse])
def get_camera_zones(camera_id: int, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam.zones


@router.put("/camera/{camera_id}", response_model=List[ParkingZoneResponse])
def set_camera_zones(camera_id: int, zone_ids: List[int], db: Session = Depends(get_db)):
    """Replace all zones for a camera with the given list of zone IDs."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    zones = db.query(ParkingZone).filter(ParkingZone.id.in_(zone_ids)).all()
    cam.zones = zones
    db.commit()
    db.refresh(cam)
    return cam.zones
