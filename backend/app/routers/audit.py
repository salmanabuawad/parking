"""Fleet-wide ticket audit trail (#12/#16) — recent actions across all tickets, for the admin
audit-history page. Complements the per-ticket GET /api/tickets/{id}/audit."""
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(limit: int = 200, ticket_id: int | None = None, action_type: str | None = None,
               db=Depends(get_db), _=Depends(get_current_user)):
    """Recent audit rows across all tickets, newest first. Optional ticket_id / action_type filters."""
    from app.models import TicketAuditLog, Inspector
    q = db.query(TicketAuditLog)
    if ticket_id is not None:
        q = q.filter(TicketAuditLog.ticket_id == ticket_id)
    if action_type:
        q = q.filter(TicketAuditLog.action_type == action_type)
    rows = q.order_by(TicketAuditLog.id.desc()).limit(min(1000, max(1, limit))).all()
    names = {i.id: i.full_name for i in db.query(Inspector).all()}
    return [{
        "id": r.id,
        "ticket_id": r.ticket_id,
        "action_type": r.action_type,
        "inspector_id": r.inspector_id,
        "inspector_name": names.get(r.inspector_id),
        "old_value": r.old_value_json,
        "new_value": r.new_value_json,
        "notes": r.notes,
        "ip_address": r.ip_address,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
