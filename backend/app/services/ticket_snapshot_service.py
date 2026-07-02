"""Build immutable snapshots of camera / section / violation-rule / system-config at ticket
creation, so historical tickets never recompute from live config (rule 8). From snippets,
adapted to the existing models (CameraSegment as the section; ViolationRule keyed by rule_id).
"""
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models import AppConfig, Camera, CameraSegment, ViolationRule


def model_to_dict(obj):
    if obj is None:
        return None
    data = {}
    for column in sa_inspect(obj).mapper.column_attrs:
        value = getattr(obj, column.key)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        data[column.key] = value
    return data


def build_ticket_snapshots(
    db: Session,
    *,
    camera_id=None,
    section_id: int | None = None,
    rule_code: str | None = None,
) -> dict:
    """Return the 4 snapshot dicts. `camera_id` may be an int, None, or a non-numeric hint
    like 'mobile' (then no camera snapshot). `rule_code` is a ViolationRule.rule_id string."""
    camera = None
    try:
        if camera_id not in (None, "", "mobile"):
            camera = db.query(Camera).filter(Camera.id == int(camera_id)).first()
    except (ValueError, TypeError):
        camera = None

    section = db.query(CameraSegment).filter(CameraSegment.id == section_id).first() if section_id else None
    rule = db.query(ViolationRule).filter(ViolationRule.rule_id == rule_code).first() if rule_code else None
    system_config = db.query(AppConfig).first()

    return {
        "camera_config_snapshot": model_to_dict(camera),
        "camera_section_snapshot": model_to_dict(section),
        "violation_rule_snapshot": model_to_dict(rule),
        "system_config_snapshot": model_to_dict(system_config),
    }
