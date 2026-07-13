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
    section_id: int | None = None,
    at: datetime | None = None,
    within_seconds: int = 300,
    exclude_id: int | None = None,
) -> Ticket | None:
    """Return an existing ticket for the same normalized plate + camera (+ section) whose CAPTURE
    time is within `within_seconds` of `at`, else None (#14). Matching on the capture moment — not
    row-creation — catches re-uploads / overlapping clips of the same violation event."""
    norm = normalize_israeli_plate(plate)
    if not norm:
        return None
    at = at or datetime.now(timezone.utc)
    lo, hi = at - timedelta(seconds=within_seconds), at + timedelta(seconds=within_seconds)
    q = (
        db.query(Ticket)
        .filter(Ticket.captured_at.isnot(None), Ticket.captured_at >= lo, Ticket.captured_at <= hi)
        .order_by(Ticket.id)
    )
    for t in q.all():
        if exclude_id and t.id == exclude_id:
            continue
        same_plate = (
            normalize_israeli_plate(t.license_plate) == norm
            or normalize_israeli_plate(getattr(t, "inspector_plate", None)) == norm
        )
        if not same_plate:
            continue
        if camera_id is not None and str(t.camera_id) != str(camera_id):
            continue
        if section_id is not None and getattr(t, "camera_section_id", None) not in (None, section_id):
            continue
        return t
    return None
