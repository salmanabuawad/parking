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


def _point_in_polygon(x: float, y: float, poly) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def find_section_for_point(db: Session, camera_id, x: float, y: float) -> int | None:
    """Return the id of the active camera section whose polygon contains (x, y) — in the camera's
    calibration pixels — else None. Lets the worker attach a ticket to its enforcement section so
    build_ticket_snapshots freezes that section into camera_section_snapshot (rule 8)."""
    if camera_id in (None, "", "mobile"):
        return None
    try:
        cid = int(camera_id)
    except (ValueError, TypeError):
        return None
    for seg in (db.query(CameraSegment)
                .filter(CameraSegment.camera_id == cid, CameraSegment.is_active.is_(True))
                .order_by(CameraSegment.display_order).all()):
        poly = seg.polygon_json
        if poly and len(poly) >= 3 and _point_in_polygon(x, y, poly):
            return seg.id
    return None


def grid_rules_for_point(camera, x: float, y: float) -> list[str]:
    """For a grid zone-map camera, return the violation rule_ids painted on the cell containing the
    point (x, y in calibration pixels) — a cell may carry 0, 1 or many types — else []. Complements
    find_section_for_point (polygons): the grid maps a car's position → cell → its violation type(s).
    Accepts both the current list shape and the legacy single-string cell shape."""
    grid = getattr(camera, "zone_grid", None) or {}
    cols, rows = grid.get("cols"), grid.get("rows")
    cells = grid.get("cells") or {}
    cw, ch = getattr(camera, "calibration_width", None), getattr(camera, "calibration_height", None)
    if not (cols and rows and cw and ch):
        return []
    c = min(int(cols) - 1, max(0, int(x * int(cols) / cw)))
    r = min(int(rows) - 1, max(0, int(y * int(rows) / ch)))
    val = cells.get(f"{c},{r}")
    if not val:
        return []
    return list(val) if isinstance(val, list) else [val]


_DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]  # datetime.weekday(): Mon=0 … Sun=6


def camera_active_at(camera, dt) -> bool:
    """Is the camera enforcing at datetime `dt`? Gated by its working days (active_days) and hours
    (active_from_time/active_to_time). An empty schedule means always active. The window is read in
    Israel local wall-clock time (schedule times are local); overnight windows (from > to) are handled."""
    if camera is None or dt is None:
        return True
    days = getattr(camera, "active_days", None) or []
    frm = getattr(camera, "active_from_time", None)
    to = getattr(camera, "active_to_time", None)
    if not days and not (frm and to):
        return True

    local = dt
    try:
        if getattr(dt, "tzinfo", None) is not None:
            from zoneinfo import ZoneInfo
            local = dt.astimezone(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        local = dt

    if days and _DOW[local.weekday()] not in days:
        return False
    if frm and to:
        hhmm = local.strftime("%H:%M")
        within = (frm <= hhmm <= to) if frm <= to else (hhmm >= frm or hhmm <= to)
        if not within:
            return False
    return True
