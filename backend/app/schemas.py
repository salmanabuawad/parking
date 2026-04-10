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
    violation_rules: Optional[list[str]] = None   # e.g. ["IL-STATIC-001", "IL-STATIC-005"]
    violation_zone: Optional[str] = None           # "red_white" | "blue_white" | None


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
    violation_rules: Optional[list[str]] = None
    violation_zone: Optional[str] = None


class CameraResponse(CameraBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Field configuration schemas
class FieldConfigurationBase(BaseModel):
    grid_name: str
    field_name: str
    width_chars: int = 10
    padding: int = 8
    hebrew_name: Optional[str] = None
    pinned: bool = False
    pin_side: Optional[str] = None
    visible: bool = True
    column_order: Optional[int] = None


class FieldConfigurationUpsert(FieldConfigurationBase):
    pass


class FieldConfigurationResponse(FieldConfigurationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FieldConfigurationBulkUpsert(BaseModel):
    items: list[FieldConfigurationUpsert]
