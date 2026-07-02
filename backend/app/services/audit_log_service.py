"""Audit-log service: record every inspector action on a ticket. From snippets."""
from sqlalchemy.orm import Session

from app.models import TicketAuditLog


def write_ticket_audit(
    db: Session,
    *,
    ticket_id: int,
    action_type: str,
    inspector_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    notes: str | None = None,
    ip_address: str | None = None,
) -> TicketAuditLog:
    row = TicketAuditLog(
        ticket_id=ticket_id,
        inspector_id=inspector_id,
        action_type=action_type,
        old_value_json=old_value,
        new_value_json=new_value,
        notes=notes,
        ip_address=ip_address,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
