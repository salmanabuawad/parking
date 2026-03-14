"""Pydantic schemas for API."""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


# Camera schemas
class CameraBase(BaseModel):
    name: str
    location: Optional[str] = None
    connection_type: str = "ip"
    connection_config: Optional[dict[str, Any]] = None
    param_source: str = "manual"
    params: Optional[dict[str, Any]] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    connection_type: Optional[str] = None
    connection_config: Optional[dict[str, Any]] = None
    param_source: Optional[str] = None
    params: Optional[dict[str, Any]] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None


class CameraResponse(CameraBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
