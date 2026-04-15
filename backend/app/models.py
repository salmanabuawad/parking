from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, LargeBinary, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base

import enum


# Junction table: camera ↔ parking zones (many-to-many)
camera_zones = Table(
    "camera_zones",
    Base.metadata,
    Column("camera_id", Integer, ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True),
    Column("zone_id", Integer, ForeignKey("parking_zones.id", ondelete="CASCADE"), primary_key=True),
)


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
    # Violation rules this camera should check (list of rule IDs, e.g. ["IL-STATIC-001", "IL-STATIC-005"])
    violation_rules = Column(JSON, nullable=True)
    # Legacy single zone hint (kept for upload jobs / backward compat)
    violation_zone = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Parking zones visible from this camera (many-to-many)
    zones = relationship("ParkingZone", secondary="camera_zones", back_populates="cameras")


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
    violation_rule_id = Column(String(30), nullable=True)       # e.g. IL-STATIC-001
    violation_decision = Column(String(30), nullable=True)      # confirmed_violation | suspected_violation | ...
    violation_confidence = Column(Float, nullable=True)         # 0.0 – 1.0
    violation_description_he = Column(Text, nullable=True)
    violation_description_en = Column(Text, nullable=True)
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
    # Digital signature of the processed (blurred) video
    video_signature = Column(Text, nullable=True)         # RSA-PSS signature hex
    video_signature_key = Column(String(50), nullable=True)  # public key fingerprint (first 16 hex chars)
    video_signed_at = Column(DateTime(timezone=True), nullable=True)
    # Vehicle data fetched from Ministry of Transport registry by plate number
    vehicle_type = Column(String(100), nullable=True)
    vehicle_color = Column(String(100), nullable=True)
    vehicle_year = Column(Integer, nullable=True)
    vehicle_make = Column(String(100), nullable=True)
    vehicle_model = Column(String(100), nullable=True)
    original_video_path = Column(String(500), nullable=True)  # unblurred original, preserved after processing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    anpr_track_results = relationship(
        "AnprTrackResult",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )


class AnprTrackResult(Base):
    """Per-track ANPR outcome persisted for dashboard / audit (Israeli private plates)."""

    __tablename__ = "anpr_track_results"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = Column(Integer, nullable=False)
    raw_digits = Column(String(16), nullable=False)
    normalized_plate = Column(String(32), nullable=False)
    vote_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="anpr_track_results")


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
    # ANPR pipeline tuning (used by upload worker -> plate_pipeline PipelineConfig)
    anpr_detector_backend = Column(String(20), default="enterprise", nullable=False)
    anpr_ocr_every_n_frames = Column(Integer, default=2, nullable=False)
    enterprise_detection_zoom = Column(Float, default=1.75, nullable=False)
    enterprise_detection_roi_y_start = Column(Float, default=0.26, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ViolationRule(Base):
    """Israeli traffic violation rule definitions (editable from admin UI)."""

    __tablename__ = "violation_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String(30), unique=True, nullable=False, index=True)   # e.g. IL-STATIC-001
    title_he = Column(String(200), nullable=False)
    title_en = Column(String(200), nullable=False)
    description_he = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    legal_basis_he = Column(Text, nullable=True)
    legal_basis_en = Column(Text, nullable=True)
    fine_ils = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ParkingZone(Base):
    """Parking zone type visible from a camera (e.g. red-white curb, blue-white curb)."""

    __tablename__ = "parking_zones"

    id = Column(Integer, primary_key=True, index=True)
    zone_code = Column(String(40), unique=True, nullable=False, index=True)  # e.g. "red_white"
    name_he = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    description_he = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    cameras = relationship("Camera", secondary="camera_zones", back_populates="zones")


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
    license_plate = Column(String(20), default="")
    violation_zone = Column(String(20), default="red_white")
    description = Column(Text, nullable=True)
    submitted_by = Column(String(50), nullable=True)
    camera_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class FieldConfiguration(Base):
    """Per-grid column configuration: width, order, visibility, pinning."""
    __tablename__ = "field_configurations"

    id = Column(Integer, primary_key=True, index=True)
    grid_name = Column(String(100), nullable=False)
    field_name = Column(String(100), nullable=False)
    width_chars = Column(Integer, nullable=False, default=10)
    padding = Column(Integer, nullable=False, default=8)
    hebrew_name = Column(String(200), nullable=True)
    pinned = Column(Boolean, nullable=False, default=False)
    pin_side = Column(String(10), nullable=True)   # 'left' | 'right' | null
    visible = Column(Boolean, nullable=False, default=True)
    column_order = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
