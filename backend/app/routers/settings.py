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


def _get_config(db: Session) -> AppConfig:
    cfg = db.query(AppConfig).first()
    if not cfg:
        cfg = AppConfig(
            id=1,
            blur_kernel_size=15,
            blur_expand_ratio=0.18,
            temporal_blur_enabled=True,
            temporal_blur_max_misses=6,
            use_violation_pipeline=True,
            anpr_detector_backend="enterprise",
            anpr_ocr_every_n_frames=2,
            enterprise_detection_zoom=1.75,
            enterprise_detection_roi_y_start=0.26,
            vehicle_registry_api_enabled=True,
            vehicle_registry_api_url="https://data.gov.il/api/3/action/datastore_search",
            vehicle_registry_resource_id="053cea08-09bc-40ec-8f7a-156f0677aff3",
            vehicle_registry_plate_field="mispar_rechev",
            vehicle_registry_timeout_seconds=10,
            vehicle_registry_cache_ttl_hours=24,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("")
def get_settings(db: Session = Depends(get_db), _=Depends(get_current_user)):
    cfg = _get_config(db)
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
    }


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

    db.commit()
    db.refresh(cfg)

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
    }


@router.put("")
def update_settings_put(
    body: SettingsUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return update_settings(body=body, db=db, _=_)
