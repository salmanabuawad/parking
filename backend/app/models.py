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
    assigned_inspector_id = Column(Integer, ForeignKey("inspectors.id"), nullable=True)  # handling inspector (#8)
    range_config = Column(JSON, nullable=True)  # camera coverage/range config (from snippets)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Parking zones visible from this camera (many-to-many)
    zones = relationship("ParkingZone", secondary="camera_zones", back_populates="cameras")
    segments = relationship(
        "CameraSegment",
        back_populates="camera",
        cascade="all, delete-orphan",
        order_by="CameraSegment.display_order",
    )


class CameraSegment(Base):
    """A labeled segment (מקטע) of a camera station's coverage, with its own violation types.

    Per-segment violation types replace the flat camera-level violation_rules list.
    """

    __tablename__ = "camera_segments"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(200), nullable=False)          # מלל ליד כל מקטע (free text)
    violation_rule_ids = Column(JSON, nullable=True)     # סוגי עבירה — list of ViolationRule.rule_id strings
    # --- Geometry (box or polygon on the camera frame) + schedule (from snippets) ---
    coordinate_type = Column(String(20), default="pixels", nullable=False)  # pixels | normalized | polygon
    x1 = Column(Float, nullable=True)
    y1 = Column(Float, nullable=True)
    x2 = Column(Float, nullable=True)
    y2 = Column(Float, nullable=True)
    polygon_json = Column(JSON, nullable=True)
    min_stay_seconds = Column(Integer, nullable=True)
    evidence_video_seconds = Column(Integer, nullable=True)
    active_days = Column(JSON, nullable=True)             # e.g. ["SUN","MON","TUE"]
    active_from_time = Column(String(10), nullable=True)  # "07:00"
    active_to_time = Column(String(10), nullable=True)    # "19:00"
    holiday_policy = Column(String(30), nullable=True)
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    camera = relationship("Camera", back_populates="segments")


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


class Inspector(Base):
    """Field enforcement officer (פקח). Logs in to review and approve reports."""

    __tablename__ = "inspectors"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    badge_number = Column(String(40), nullable=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(120), nullable=True)
    role = Column(String(20), default="inspector", nullable=False)  # inspector | supervisor
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


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
    upload_job_id = Column(Integer, nullable=True, index=True)  # links N tickets (one per car) to the source job/video
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
    # --- Violation window (auto-filled from the clip; inspector-editable) ---
    violation_start_at = Column(DateTime(timezone=True), nullable=True)
    violation_end_at = Column(DateTime(timezone=True), nullable=True)
    # --- Inspector approval fields ---
    approved_by_inspector_id = Column(Integer, ForeignKey("inspectors.id"), nullable=True, index=True)
    assigned_inspector_id = Column(Integer, ForeignKey("inspectors.id"), nullable=True, index=True)  # inbox owner / handler (#9)
    inspector_approved_at = Column(DateTime(timezone=True), nullable=True)
    inspector_violation_rule_id = Column(String(30), nullable=True)   # violation type chosen by the inspector (rule_id)
    inspector_plate = Column(String(20), nullable=True)               # plate confirmed by the inspector (must match detected)
    # --- Extended inspector review (snippets merge) ---
    inspector_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    inspector_decision = Column(String(30), nullable=True)            # approved | rejected
    review_status = Column(String(40), nullable=True)                 # manual_review_required | approved | rejected
    violation_duration_seconds = Column(Float, nullable=True)
    camera_section_id = Column(Integer, ForeignKey("camera_segments.id"), nullable=True)
    inspector_vehicle_color = Column(String(100), nullable=True)
    inspector_vehicle_type = Column(String(100), nullable=True)
    inspector_vehicle_make = Column(String(100), nullable=True)
    inspector_vehicle_model = Column(String(100), nullable=True)
    # --- Registry lookup snapshot (make/model/color/year reuse vehicle_* above) ---
    vehicle_registry_lookup_status = Column(String(40), nullable=True)  # plate_found | plate_not_found | invalid_plate | lookup_failed
    vehicle_registry_raw_json = Column(JSON, nullable=True)
    vehicle_registry_checked_at = Column(DateTime(timezone=True), nullable=True)
    # --- 4 evidence images (screenshot ids) ---
    start_violation_screenshot_id = Column(Integer, nullable=True)
    end_violation_screenshot_id = Column(Integer, nullable=True)
    clear_plate_screenshot_id = Column(Integer, nullable=True)
    violation_context_screenshot_id = Column(Integer, nullable=True)
    # --- Suspected-vehicle marker (green pending -> red approved) ---
    suspected_vehicle_box = Column(JSON, nullable=True)
    suspected_vehicle_track_id = Column(String(40), nullable=True)
    suspected_vehicle_marker_state = Column(String(20), default="pending", nullable=False)
    # --- Immutable snapshots at creation (never recomputed from live config) ---
    camera_config_snapshot = Column(JSON, nullable=True)
    camera_section_snapshot = Column(JSON, nullable=True)
    violation_rule_snapshot = Column(JSON, nullable=True)
    system_config_snapshot = Column(JSON, nullable=True)
    # --- Evidence integrity hashes ---
    original_video_sha256 = Column(String(64), nullable=True)
    evidence_video_sha256 = Column(String(64), nullable=True)
    best_frame_sha256 = Column(String(64), nullable=True)
    plate_crop_sha256 = Column(String(64), nullable=True)

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
    role = Column(String(40), nullable=True)  # violation_start | violation_end | plate_clear | violation_evidence (#7.4)
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

    # Israeli Ministry of Transport vehicle registry lookup (data.gov.il CKAN API)
    vehicle_registry_api_enabled = Column(Boolean, default=True, nullable=False)
    vehicle_registry_api_url = Column(
        String(500),
        default="https://data.gov.il/api/3/action/datastore_search",
        nullable=False,
    )
    vehicle_registry_resource_id = Column(
        String(80),
        default="053cea08-09bc-40ec-8f7a-156f0677aff3",
        nullable=False,
    )
    vehicle_registry_plate_field = Column(String(80), default="mispar_rechev", nullable=False)
    vehicle_registry_timeout_seconds = Column(Integer, default=10, nullable=False)
    vehicle_registry_cache_ttl_hours = Column(Integer, default=24, nullable=False)

    # --- Enforcement / system settings (editable from UI) ---
    violation_dwell_seconds = Column(Integer, default=300, nullable=False)    # standing time that counts as a violation
    required_video_seconds = Column(Integer, default=10, nullable=False)      # required clip length for a valid report
    video_retention_days = Column(Integer, default=90, nullable=False)        # how long processed videos are kept
    video_timestamp_overlay = Column(Boolean, default=True, nullable=False)   # burn a real-time clock into result videos

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
    # --- Evidence + timing requirements (violation-type catalog, from snippets) ---
    default_min_stay_seconds = Column(Integer, default=30, nullable=False)
    default_evidence_video_seconds = Column(Integer, default=20, nullable=False)
    requires_start_image = Column(Boolean, default=True, nullable=False)
    requires_end_image = Column(Boolean, default=True, nullable=False)
    requires_clear_plate_image = Column(Boolean, default=True, nullable=False)
    requires_context_image = Column(Boolean, default=True, nullable=False)
    requires_continuous_video = Column(Boolean, default=True, nullable=False)
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


class TicketAuditLog(Base):
    """Immutable audit trail of every inspector action on a ticket (from snippets)."""

    __tablename__ = "ticket_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    inspector_id = Column(Integer, ForeignKey("inspectors.id"), nullable=True, index=True)
    action_type = Column(String(50), nullable=False, index=True)
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VehicleExemption(Base):
    """Whitelist / exemption for specific plates (from snippets)."""

    __tablename__ = "vehicle_exemptions"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(20), nullable=False, index=True)
    exemption_type = Column(String(50), nullable=False)   # diplomat | police | resident | disabled | ...
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


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
