"""Inspector review orchestration (rule 6: logic in services). From snippets, adapted to the
existing ticket field names. Validates the plate (7/8 digits), looks up + snapshots the registry
result, enforces the 4-image gate on approval, keeps the existing `status` flow in sync, and
writes an audit-log entry for every action (rule 7).
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Ticket
from app.services.audit_log_service import write_ticket_audit
from app.services.israeli_plate import normalize_israeli_plate
from app.services.ticket_workflow_service import validate_ticket_before_approval
from app.services.vehicle_registry_api import lookup_vehicle_by_plate

# The 4 evidence-image roles (#7.4) map to these ticket FK columns; the ticket_screenshots router
# keeps one image per role, so resolution is unambiguous.
_ROLE_TO_FK = {
    "violation_start": "start_violation_screenshot_id",
    "violation_end": "end_violation_screenshot_id",
    "plate_clear": "clear_plate_screenshot_id",
    "violation_evidence": "violation_context_screenshot_id",
}


def _resolve_evidence_screenshots(db: Session, ticket: Ticket) -> None:
    """Populate the 4 evidence-image FK columns from the ticket's role-tagged screenshots (#7.4)."""
    from app.models import TicketScreenshot
    by_role: dict[str, int] = {}
    for s in db.query(TicketScreenshot).filter(TicketScreenshot.ticket_id == ticket.id).all():
        r = getattr(s, "role", None)
        if r in _ROLE_TO_FK:
            by_role[r] = s.id
    for role, fk in _ROLE_TO_FK.items():
        sid = by_role.get(role)
        if sid and hasattr(ticket, fk):
            setattr(ticket, fk, sid)


def _review_fields(t: Ticket) -> dict:
    return {
        "inspector_violation_rule_id": t.inspector_violation_rule_id,
        "inspector_plate": t.inspector_plate,
        "inspector_vehicle_color": t.inspector_vehicle_color,
        "inspector_vehicle_type": t.inspector_vehicle_type,
        "inspector_vehicle_make": t.inspector_vehicle_make,
        "inspector_vehicle_model": t.inspector_vehicle_model,
        "inspector_decision": t.inspector_decision,
        "status": t.status,
    }


def update_ticket_by_inspector(
    db: Session,
    *,
    ticket_id: int,
    inspector_id: int,
    data: dict,
    ip_address: str | None = None,
) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_value = _review_fields(ticket)

    if "violation_rule_id" in data:
        ticket.inspector_violation_rule_id = data["violation_rule_id"]
    if "vehicle_color" in data:
        ticket.inspector_vehicle_color = data["vehicle_color"]
    if "vehicle_type" in data:
        ticket.inspector_vehicle_type = data["vehicle_type"]
    if "vehicle_make" in data:
        ticket.inspector_vehicle_make = data["vehicle_make"]
    if "vehicle_model" in data:
        ticket.inspector_vehicle_model = data["vehicle_model"]
    if data.get("fine_amount") is not None:
        ticket.fine_amount = data["fine_amount"]
    if data.get("admin_notes") is not None:
        ticket.admin_notes = data["admin_notes"]

    if data.get("violation_start_at") is not None:
        ticket.violation_start_at = data["violation_start_at"]
    if data.get("violation_end_at") is not None:
        ticket.violation_end_at = data["violation_end_at"]
    if ticket.violation_start_at and ticket.violation_end_at:
        try:
            ticket.violation_duration_seconds = (ticket.violation_end_at - ticket.violation_start_at).total_seconds()
        except Exception:
            pass

    if data.get("plate_number"):
        normalized = normalize_israeli_plate(data["plate_number"])
        if not normalized:
            raise HTTPException(status_code=400, detail="מספר רכב לא תקין. נדרשים 7 או 8 ספרות.")
        ticket.inspector_plate = normalized

        registry_result = lookup_vehicle_by_plate(db, normalized)
        ticket.vehicle_registry_lookup_status = registry_result.get("status")
        ticket.vehicle_registry_raw_json = registry_result
        ticket.vehicle_registry_checked_at = datetime.now(timezone.utc)
        from app.services.vehicle_lookup import record_to_vehicle_fields
        for _f, _v in record_to_vehicle_fields(registry_result.get("record")).items():
            setattr(ticket, _f, _v)
        ocr_norm = normalize_israeli_plate(ticket.license_plate)
        if ocr_norm and ocr_norm != normalized:
            ticket.review_status = "manual_review_required"

    if data.get("approve") is True:
        # Resolve the 4 role-tagged evidence screenshots to the ticket FK columns (#7.4), then gate.
        _resolve_evidence_screenshots(db, ticket)
        from app.config import settings
        if getattr(settings, "require_evidence_images", False):
            validate_ticket_before_approval(ticket)
        now = datetime.now(timezone.utc)
        ticket.inspector_decision = "approved"
        ticket.review_status = "approved"
        ticket.status = "approved"
        ticket.approved_by_inspector_id = inspector_id
        ticket.inspector_reviewed_at = now
        ticket.inspector_approved_at = now
        ticket.reviewed_at = now
        ticket.suspected_vehicle_marker_state = "approved"

    if data.get("reject") is True:
        reason = data.get("rejection_reason")
        notes = data.get("notes")
        if not reason:
            raise HTTPException(status_code=400, detail="נדרשת סיבת דחייה.")
        if reason == "other" and not notes:
            raise HTTPException(status_code=400, detail="נדרשות הערות כאשר סיבת הדחייה היא 'אחר'.")
        now = datetime.now(timezone.utc)
        ticket.inspector_decision = "rejected"
        ticket.review_status = "rejected"
        ticket.status = "rejected"
        ticket.inspector_reviewed_at = now
        ticket.reviewed_at = now

    db.commit()
    db.refresh(ticket)

    action = "inspector_approve" if data.get("approve") else ("inspector_reject" if data.get("reject") else "inspector_update")
    write_ticket_audit(
        db, ticket_id=ticket.id, inspector_id=inspector_id, action_type=action,
        old_value=old_value, new_value=_review_fields(ticket), notes=data.get("notes"), ip_address=ip_address,
    )
    return ticket
