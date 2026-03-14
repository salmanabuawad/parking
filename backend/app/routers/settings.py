"""App settings API - configurable from UI."""
from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.database import get_db
from app.models import AppConfig
from app.auth import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    blur_kernel_size: Optional[int] = None  # 0=off, 3=very light, 5-51=medium-heavy
    use_violation_pipeline: Optional[bool] = None


def _get_config(db: Session) -> AppConfig:
    cfg = db.query(AppConfig).first()
    if not cfg:
        cfg = AppConfig(id=1, blur_kernel_size=3, use_violation_pipeline=True)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("")
def get_settings(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Get app settings (blur level, etc.)."""
    cfg = _get_config(db)
    return {
        "blur_kernel_size": cfg.blur_kernel_size,
        "use_violation_pipeline": cfg.use_violation_pipeline,
    }


@router.patch("")
def update_settings(
    body: SettingsUpdate = Body(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Update app settings. blur_kernel_size: 0=off, 3=very light, 5-51=medium-heavy."""
    cfg = _get_config(db)
    if body.blur_kernel_size is not None:
        val = max(0, min(99, body.blur_kernel_size))
        if val > 0 and val % 2 == 0:
            val += 1
        cfg.blur_kernel_size = val
    if body.use_violation_pipeline is not None:
        cfg.use_violation_pipeline = body.use_violation_pipeline
    db.commit()
    db.refresh(cfg)
    return {
        "blur_kernel_size": cfg.blur_kernel_size,
        "use_violation_pipeline": cfg.use_violation_pipeline,
    }
