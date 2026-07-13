"""Pydantic schemas for API."""
from pydantic import BaseModel, Field, model_validator
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
    assigned_inspector_id: Optional[int] = None    # handling inspector (#8) / default inspector
    # Zone-configuration: snapshot + calibration for drawing enforcement sections on the image
    source_type: Optional[str] = None              # rtsp | uploaded_image | uploaded_video
    rtsp_url: Optional[str] = None
    snapshot_path: Optional[str] = None
    calibration_width: Optional[int] = None
    calibration_height: Optional[int] = None
    zone_grid: Optional[dict[str, Any]] = None     # {"cols","rows","cells":{"c,r":[rule_id, ...]}}
    latitude: Optional[float] = None               # map placement (WGS84)
    longitude: Optional[float] = None
    status: Optional[str] = "online"               # online | offline | maintenance | error
    city: Optional[str] = None                     # fleet dashboard grouping
    active_schedule: Optional[dict[str, Any]] = None   # {"SUN": {"from":"07:00","to":"19:00"}, ...}
    active_days: Optional[list[str]] = None        # legacy flat schedule (superseded by active_schedule)
    active_from_time: Optional[str] = None
    active_to_time: Optional[str] = None


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
    assigned_inspector_id: Optional[int] = None
    source_type: Optional[str] = None
    rtsp_url: Optional[str] = None
    snapshot_path: Optional[str] = None
    calibration_width: Optional[int] = None
    calibration_height: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    city: Optional[str] = None
    active_schedule: Optional[dict[str, Any]] = None
    active_days: Optional[list[str]] = None
    active_from_time: Optional[str] = None
    active_to_time: Optional[str] = None


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
    role: str = "inspector"            # "inspector" (פקח) only
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
    label: str = Field(min_length=1, max_length=200)
    violation_rule_ids: Optional[list[str]] = None   # e.g. ["IL-STATIC-001", "IL-STATIC-005"]
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True
    # Geometry (#4) — where in the frame the segment sits
    coordinate_type: Optional[str] = "pixels"        # pixels | normalized | polygon
    x1: Optional[float] = None
    y1: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None
    polygon_json: Optional[list] = None
    # Per-segment overrides + schedule (#1, #4)
    min_stay_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    evidence_video_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    active_days: Optional[list[str]] = None          # ["SUN","MON",...]
    active_from_time: Optional[str] = None           # "07:00"
    active_to_time: Optional[str] = None             # "19:00"
    holiday_policy: Optional[str] = None

    @model_validator(mode="after")
    def validate_geometry_and_rules(self):
        # A zone may carry 0, 1, or many violation types (#4/#10) — no minimum enforced here.
        if self.polygon_json:
            if len(self.polygon_json) < 3:
                raise ValueError("פוליגון מקטע חייב להכיל לפחות 3 נקודות")
        elif None not in (self.x1, self.y1, self.x2, self.y2):
            if self.x2 <= self.x1 or self.y2 <= self.y1:
                raise ValueError("קואורדינטות המקטע אינן תקינות")
        else:
            raise ValueError("יש להגדיר מלבן או פוליגון למקטע")
        return self


class CameraSegmentCreate(CameraSegmentBase):
    pass


class CameraSegmentUpdate(BaseModel):
    label: Optional[str] = None
    violation_rule_ids: Optional[list[str]] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    coordinate_type: Optional[str] = None
    x1: Optional[float] = None
    y1: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None
    polygon_json: Optional[list] = None
    min_stay_seconds: Optional[int] = None
    evidence_video_seconds: Optional[int] = None
    active_days: Optional[list[str]] = None
    active_from_time: Optional[str] = None
    active_to_time: Optional[str] = None
    holiday_policy: Optional[str] = None


class CameraSegmentResponse(CameraSegmentBase):
    id: int
    camera_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
