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
    assigned_inspector_id: Optional[int] = None    # handling inspector (#8)


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


# Inspector (פקח) schemas
class InspectorBase(BaseModel):
    username: str
    full_name: str
    badge_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: str = "inspector"            # "inspector" | "supervisor"
    is_active: bool = True


class InspectorCreate(InspectorBase):
    password: str


class InspectorUpdate(BaseModel):
    full_name: Optional[str] = None
    badge_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None     # provide to change the password


class InspectorResponse(InspectorBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Camera segment (מקטע) schemas
class CameraSegmentBase(BaseModel):
    label: str
    violation_rule_ids: Optional[list[str]] = None   # e.g. ["IL-STATIC-001", "IL-STATIC-005"]
    display_order: int = 0
    is_active: bool = True


class CameraSegmentCreate(CameraSegmentBase):
    pass


class CameraSegmentUpdate(BaseModel):
    label: Optional[str] = None
    violation_rule_ids: Optional[list[str]] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class CameraSegmentResponse(CameraSegmentBase):
    id: int
    camera_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
