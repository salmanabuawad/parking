from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, Boolean, JSON, LargeBinary, Float
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
    """Street camera configuration. Params can be defined manually or from manufacturer manual."""
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(255), nullable=True)

    # Connection: IP, Bluetooth, WiFi router, RTSP, USB, or any supported mechanism
    connection_type = Column(String(20), nullable=False, default=ConnectionType.IP.value)
    connection_config = Column(JSON, nullable=True)
    # Examples: {"ip": "192.168.1.100", "port": 554} | {"bluetooth_addr": "..."} | {"ssid": "...", "password": "..."}

    # Parameters: manual or from manufacturer manual
    param_source = Column(String(25), default=ParamSource.MANUAL.value)
    params = Column(JSON, nullable=True)
    # Examples: {"moving": true, "night_light": true, "resolution": "1080p", "fps": 30}
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CameraVideo(Base):
    """Video stored in DB, linked to a camera (e.g. sample footage)."""
    __tablename__ = "camera_videos"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, nullable=True)  # FK to cameras.id
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
    plate_detection_reason = Column(Text, nullable=True)  # why OCR failed when plate is 11111
    plate_format = Column(String(50), nullable=True)  # ref: private_long, private_rect, motorcycle, scooter
    camera_id = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    violation_zone = Column(String(20), nullable=True)  # red_white or blue_white
    description = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    fine_amount = Column(Integer, nullable=True)  # in cents
    status = Column(String(20), default=TicketStatus.PENDING_REVIEW.value)
    video_path = Column(String(500), nullable=True)  # path to blurred video
    ticket_image_path = Column(String(500), nullable=True)  # extracted frame for final ticket
    video_id = Column(Integer, nullable=True)  # FK to camera_videos.id (video in DB)
    processed_video_id = Column(Integer, nullable=True)  # blurred video in camera_videos
    ticket_image_id = Column(Integer, nullable=True)  # extracted frame (JPEG) in camera_videos
    latitude = Column(Float, nullable=True)  # GPS from mobile upload
    longitude = Column(Float, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)  # time when video was captured on device
    video_params = Column(JSON, nullable=True)  # extracted from video: GPS, duration, resolution, codec, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)


class AppConfig(Base):
    """App-wide config (blur level, pipeline options). Single row, editable from UI."""
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    blur_kernel_size = Column(Integer, default=3, nullable=False)  # 0=off, 3=very light, 51=heavy
    use_violation_pipeline = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UploadJob(Base):
    """Queue for mobile uploads: accept video, return ACK, process in background."""
    __tablename__ = "upload_jobs"

    id = Column(Integer, primary_key=True, index=True)
    raw_video_id = Column(Integer, nullable=True)  # legacy: FK camera_videos.id
    raw_video_path = Column(String(500), nullable=True)  # path under videos/ e.g. raw/uuid.mp4
    status = Column(String(20), default="queued")  # queued, processing, completed, failed
    processing_started_at = Column(DateTime(timezone=True), nullable=True)  # when status was set to processing
    ticket_id = Column(Integer, nullable=True)  # set when completed
    error_message = Column(Text, nullable=True)
    # Form data from upload (for ticket creation)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    license_plate = Column(String(20), default="11111")
    violation_zone = Column(String(20), default="red_white")
    description = Column(Text, nullable=True)
    submitted_by = Column(String(50), nullable=True)  # username
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
