"""App settings API - configurable from UI."""

from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AppConfig

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    blur_kernel_size: Optional[int] = None
    blur_expand_ratio: Optional[float] = None
    temporal_blur_enabled: Optional[bool] = None
    temporal_blur_max_misses: Optional[int] = None
    use_violation_pipeline: Optional[bool] = None
    anpr_detector_backend: Optional[str] = None
    anpr_ocr_every_n_frames: Optional[int] = None
    enterprise_detection_zoom: Optional[float] = None
    enterprise_detection_roi_y_start: Optional[float] = None
    vehicle_registry_api_enabled: Optional[bool] = None
    vehicle_registry_api_url: Optional[str] = None
    vehicle_registry_resource_id: Optional[str] = None
    vehicle_registry_plate_field: Optional[str] = None
    vehicle_registry_timeout_seconds: Optional[int] = None
    vehicle_registry_cache_ttl_hours: Optional[int] = None
    # --- enforcement / system settings ---
    violation_dwell_seconds: Optional[int] = None
    required_video_seconds: Optional[int] = None
    video_retention_days: Optional[int] = None
    evidence_video_pre_seconds: Optional[int] = None
    evidence_video_post_seconds: Optional[int] = None
    original_video_retention_days: Optional[int] = None
    processed_video_retention_days: Optional[int] = None
    ticket_candidate_retention_days: Optional[int] = None
    video_timestamp_overlay: Optional[bool] = None
    city_order: Optional[list[str]] = None


def _get_config(db: Session) -> AppConfig:
    cfg = db.query(AppConfig).first()
    if not cfg:
        cfg = AppConfig(id=1)  # column defaults fill the rest
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _serialize(cfg: AppConfig) -> dict:
    return {
        "blur_kernel_size": cfg.blur_kernel_size,
        "blur_expand_ratio": cfg.blur_expand_ratio,
        "temporal_blur_enabled": cfg.temporal_blur_enabled,
        "temporal_blur_max_misses": cfg.temporal_blur_max_misses,
        "use_violation_pipeline": cfg.use_violation_pipeline,
        "anpr_detector_backend": cfg.anpr_detector_backend,
        "anpr_ocr_every_n_frames": cfg.anpr_ocr_every_n_frames,
        "enterprise_detection_zoom": cfg.enterprise_detection_zoom,
        "enterprise_detection_roi_y_start": cfg.enterprise_detection_roi_y_start,
        "vehicle_registry_api_enabled": cfg.vehicle_registry_api_enabled,
        "vehicle_registry_api_url": cfg.vehicle_registry_api_url,
        "vehicle_registry_resource_id": cfg.vehicle_registry_resource_id,
        "vehicle_registry_plate_field": cfg.vehicle_registry_plate_field,
        "vehicle_registry_timeout_seconds": cfg.vehicle_registry_timeout_seconds,
        "vehicle_registry_cache_ttl_hours": cfg.vehicle_registry_cache_ttl_hours,
        "violation_dwell_seconds": cfg.violation_dwell_seconds,
        "required_video_seconds": cfg.required_video_seconds,
        "video_retention_days": cfg.video_retention_days,
        "evidence_video_pre_seconds": cfg.evidence_video_pre_seconds,
        "evidence_video_post_seconds": cfg.evidence_video_post_seconds,
        "original_video_retention_days": cfg.original_video_retention_days,
        "processed_video_retention_days": cfg.processed_video_retention_days,
        "ticket_candidate_retention_days": cfg.ticket_candidate_retention_days,
        "video_timestamp_overlay": cfg.video_timestamp_overlay,
        "city_order": cfg.city_order or [],
    }


@router.get("")
def get_settings(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return _serialize(_get_config(db))


@router.patch("")
def update_settings(
    body: SettingsUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cfg = _get_config(db)

    if body.blur_kernel_size is not None:
        val = max(0, min(99, int(body.blur_kernel_size)))
        if val > 0 and val % 2 == 0:
            val += 1
        cfg.blur_kernel_size = val

    if body.blur_expand_ratio is not None:
        cfg.blur_expand_ratio = max(0.0, min(1.0, float(body.blur_expand_ratio)))

    if body.temporal_blur_enabled is not None:
        cfg.temporal_blur_enabled = bool(body.temporal_blur_enabled)

    if body.temporal_blur_max_misses is not None:
        cfg.temporal_blur_max_misses = max(0, min(30, int(body.temporal_blur_max_misses)))

    if body.use_violation_pipeline is not None:
        cfg.use_violation_pipeline = body.use_violation_pipeline

    if body.anpr_detector_backend is not None:
        val = str(body.anpr_detector_backend).strip().lower()
        if val in {"hsv", "yolo", "enterprise"}:
            cfg.anpr_detector_backend = val

    if body.anpr_ocr_every_n_frames is not None:
        cfg.anpr_ocr_every_n_frames = max(1, min(10, int(body.anpr_ocr_every_n_frames)))

    if body.enterprise_detection_zoom is not None:
        cfg.enterprise_detection_zoom = max(1.0, min(4.0, float(body.enterprise_detection_zoom)))

    if body.enterprise_detection_roi_y_start is not None:
        cfg.enterprise_detection_roi_y_start = max(0.0, min(0.85, float(body.enterprise_detection_roi_y_start)))

    if body.vehicle_registry_api_enabled is not None:
        cfg.vehicle_registry_api_enabled = bool(body.vehicle_registry_api_enabled)

    if body.vehicle_registry_api_url is not None:
        val = str(body.vehicle_registry_api_url).strip()
        if val.startswith("https://") or val.startswith("http://"):
            cfg.vehicle_registry_api_url = val[:500]

    if body.vehicle_registry_resource_id is not None:
        val = str(body.vehicle_registry_resource_id).strip()
        if val:
            cfg.vehicle_registry_resource_id = val[:80]

    if body.vehicle_registry_plate_field is not None:
        val = str(body.vehicle_registry_plate_field).strip()
        if val:
            cfg.vehicle_registry_plate_field = val[:80]

    if body.vehicle_registry_timeout_seconds is not None:
        cfg.vehicle_registry_timeout_seconds = max(1, min(60, int(body.vehicle_registry_timeout_seconds)))

    if body.vehicle_registry_cache_ttl_hours is not None:
        cfg.vehicle_registry_cache_ttl_hours = max(1, min(24 * 30, int(body.vehicle_registry_cache_ttl_hours)))

    if body.violation_dwell_seconds is not None:
        cfg.violation_dwell_seconds = max(0, min(86400, int(body.violation_dwell_seconds)))

    if body.required_video_seconds is not None:
        cfg.required_video_seconds = max(0, min(3600, int(body.required_video_seconds)))

    if body.evidence_video_pre_seconds is not None:
        cfg.evidence_video_pre_seconds = max(0, min(120, int(body.evidence_video_pre_seconds)))

    if body.evidence_video_post_seconds is not None:
        cfg.evidence_video_post_seconds = max(0, min(120, int(body.evidence_video_post_seconds)))

    if body.video_retention_days is not None:
        cfg.video_retention_days = max(0, min(3650, int(body.video_retention_days)))

    if body.original_video_retention_days is not None:
        cfg.original_video_retention_days = max(0, min(3650, int(body.original_video_retention_days)))

    if body.processed_video_retention_days is not None:
        cfg.processed_video_retention_days = max(0, min(3650, int(body.processed_video_retention_days)))

    if body.ticket_candidate_retention_days is not None:
        cfg.ticket_candidate_retention_days = max(0, min(3650, int(body.ticket_candidate_retention_days)))

    if body.video_timestamp_overlay is not None:
        cfg.video_timestamp_overlay = bool(body.video_timestamp_overlay)

    if body.city_order is not None:
        # Store a de-duplicated list of non-empty city keys, preserving the given order.
        seen: set[str] = set()
        order: list[str] = []
        for k in body.city_order:
            key = str(k).strip()
            if key and key not in seen:
                seen.add(key)
                order.append(key)
        cfg.city_order = order

    db.commit()
    db.refresh(cfg)
    return _serialize(cfg)


@router.put("")
def update_settings_put(
    body: SettingsUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return update_settings(body=body, db=db, _=_)
