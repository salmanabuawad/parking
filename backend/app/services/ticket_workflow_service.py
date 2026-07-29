"""Ticket workflow gates. From snippets — require the 4 evidence images before approval."""
from fastapi import HTTPException


def validate_ticket_before_approval(ticket) -> None:
    missing = []
    # Violation start/end are TIMESTAMPS the inspector records from the video clock (pause + click),
    # not screenshots — so the gate requires the times, plus the two evidence images.
    if not ticket.violation_start_at:
        missing.append("violation_start_at")
    if not ticket.violation_end_at:
        missing.append("violation_end_at")
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
