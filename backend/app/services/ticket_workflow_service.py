"""Ticket workflow gates. From snippets — require the 4 evidence images before approval."""
from fastapi import HTTPException


def validate_ticket_before_approval(ticket) -> None:
    missing = []
    if not ticket.start_violation_screenshot_id:
        missing.append("start_violation_screenshot_id")
    if not ticket.end_violation_screenshot_id:
        missing.append("end_violation_screenshot_id")
    if not ticket.clear_plate_screenshot_id:
        missing.append("clear_plate_screenshot_id")
    if not ticket.violation_context_screenshot_id:
        missing.append("violation_context_screenshot_id")
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "לא ניתן לאשר את הדוח — חסרות תמונות ראיה נדרשות.",
                "missing_fields": missing,
            },
        )
