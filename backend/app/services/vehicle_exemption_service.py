"""Vehicle exemptions (whitelist) + duplicate-ticket prevention. Requirements 13 + 14."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Ticket, VehicleExemption
from app.services.israeli_plate import normalize_israeli_plate


def is_plate_exempt(db: Session, plate: str | None, at: datetime | None = None) -> bool:
    """True when an active, in-window exemption exists for this plate."""
    norm = normalize_israeli_plate(plate)
    if not norm:
        return False
    at = at or datetime.now(timezone.utc)
    rows = (
        db.query(VehicleExemption)
        .filter(VehicleExemption.is_active.is_(True), VehicleExemption.plate_number == norm)
        .all()
    )
    for ex in rows:
        if ex.valid_from and ex.valid_from > at:
            continue
        if ex.valid_until and ex.valid_until < at:
            continue
        return True
    return False


def find_duplicate_ticket(
    db: Session,
    *,
    plate: str | None,
    camera_id=None,
    within_seconds: int = 300,
    exclude_id: int | None = None,
) -> Ticket | None:
    """Return an existing recent ticket for the same plate (+camera) within the window, else None."""
    norm = normalize_israeli_plate(plate)
    if not norm:
        return None
    since = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
    for t in db.query(Ticket).filter(Ticket.created_at >= since).all():
        if exclude_id and t.id == exclude_id:
            continue
        same_plate = normalize_israeli_plate(t.license_plate) == norm or normalize_israeli_plate(getattr(t, "inspector_plate", None)) == norm
        if same_plate and (camera_id is None or str(t.camera_id) == str(camera_id)):
            return t
    return None
