from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, LargeBinary, Float, ForeignKey
from sqlalchemy.sql import func

from .database import Base

import enum


class ConnectionType(str, enum.Enum):
    IP = "ip"
    BLUETOOTH = "bluetooth"
    WIFI = "wifi"
    USB = "usb"
    RTSP = "rtsp"
    OTHER = "other"


class ParamSource(str, enum.Enum):
    MANUAL = "manual"
    MANUFACTURER_MANUAL = "manufacturer_manual"


class Camera(Base):
    """Street camera configuration.

    Params can be defined manually or from manufacturer manual.
    """

    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(255), nullable=True)
    connection_type = Column(String(20), nullable=False, default=ConnectionType.IP.value)
    connection_config = Column(JSON, nullable=True)
    param_source = Column(String(25), default=ParamSource.MANUAL.value)
    params = Column(JSON, nullable=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CameraVideo(Base):
    """Video stored in DB, linked to a camera (e.g. sample footage)."""

    __tablename__ = "camera_videos"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, nullable=True)
    name = Column(String(100), nullable=True)
    data = Column(LargeBinary, nullable=False)
    content_type = Column(String(50), default="video/mp4")
    duration_sec = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Admin(Base):
    """Admin user for ticket review/approval."""

    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TicketStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FINAL = "final"


class ViolationZone(str, enum.Enum):
    RED_WHITE = "red_white"
    BLUE_WHITE = "blue_white"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String(20), nullable=False)
    plate_detection_reason = Column(Text, nullable=True)
    plate_format = Column(String(50), nullable=True)
    camera_id = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    violation_zone = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    fine_amount = Column(Integer, nullable=True)
    status = Column(String(20), default=TicketStatus.PENDING_REVIEW.value)
    video_path = Column(String(500), nullable=True)
    ticket_image_path = Column(String(500), nullable=True)
    video_id = Column(Integer, nullable=True)
    processed_video_id = Column(Integer, nullable=True)
    ticket_image_id = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    video_params = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)


class TicketScreenshot(Base):
    """Screenshot attached to a ticket (blurred evidence). Supports both Alembic and simple schema."""

    __tablename__ = "ticket_screenshots"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    # Alembic schema
    image_path = Column(String(500), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    frame_timestamp_ms = Column(Integer, nullable=True)
    video_timestamp_text = Column(String(64), nullable=True)
    source_video_hash = Column(String(128), nullable=True)
    captured_by = Column(String(100), nullable=True)
    capture_note = Column(Text, nullable=True)
    frame_width = Column(Integer, nullable=True)
    frame_height = Column(Integer, nullable=True)
    is_blurred_source = Column(Boolean, nullable=True, default=True)
    # Simple schema (migrate_ticket_screenshots / init_db)
    storage_path = Column(String(500), nullable=True)
    frame_time_sec = Column(Float, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)


class AppConfig(Base):
    """App-wide config (blur level, pipeline options).

    Single row, editable from UI.
    """

    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    blur_kernel_size = Column(Integer, default=3, nullable=False)
    blur_expand_ratio = Column(Float, default=0.18, nullable=False)
    temporal_blur_enabled = Column(Boolean, default=True, nullable=False)
    temporal_blur_max_misses = Column(Integer, default=6, nullable=False)
    use_violation_pipeline = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UploadJob(Base):
    """Queue for mobile uploads: accept video, return ACK, process in background."""

    __tablename__ = "upload_jobs"

    id = Column(Integer, primary_key=True, index=True)
    raw_video_id = Column(Integer, nullable=True)
    raw_video_path = Column(String(500), nullable=True)
    status = Column(String(20), default="queued")
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    ticket_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    license_plate = Column(String(20), default="11111")
    violation_zone = Column(String(20), default="red_white")
    description = Column(Text, nullable=True)
    submitted_by = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
