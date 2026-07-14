from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import get_current_user, get_current_inspector
from app.database import get_db
from app.dependencies import get_camera_video_repo, get_ticket_repo, get_upload_job_repo
from app.models import AppConfig
from app.repositories import CameraVideoRepository, TicketRepository, UploadJobRepository
from app.services.video_processor import process_video

try:
    from app.config import settings
except Exception:
    class _FallbackSettings:
        videos_dir = Path("videos")
    settings = _FallbackSettings()

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _require_evidence_images() -> bool:
    from app.config import settings
    return bool(getattr(settings, "require_evidence_images", False))


def _ticket_dict(t) -> dict:
    return {
        "id": t.id,
        "license_plate": t.license_plate,
        "status": t.status,
        "location": t.location,
        "violation_zone": t.violation_zone,
        "description": t.description,
        "admin_notes": t.admin_notes,
        "fine_amount": t.fine_amount,
        "latitude": t.latitude,
        "longitude": t.longitude,
        "captured_at": t.captured_at.isoformat() if t.captured_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None,
        "plate_detection_reason": t.plate_detection_reason,
        "violation_rule_id": getattr(t, "violation_rule_id", None),
        "violation_decision": getattr(t, "violation_decision", None),
        "violation_confidence": getattr(t, "violation_confidence", None),
        "violation_description_he": getattr(t, "violation_description_he", None),
        "violation_description_en": getattr(t, "violation_description_en", None),
        # Original video (unblurred, preserved after processing)
        "has_original_video": bool(getattr(t, "original_video_path", None)),
        # Digital signing
        "video_signature_key": getattr(t, "video_signature_key", None),
        "video_signed_at": t.video_signed_at.isoformat() if getattr(t, "video_signed_at", None) else None,
        # Vehicle data from registry
        "vehicle_type":  getattr(t, "vehicle_type", None),
        "vehicle_color": getattr(t, "vehicle_color", None),
        "vehicle_year":  getattr(t, "vehicle_year", None),
        "vehicle_make":  getattr(t, "vehicle_make", None),
        "vehicle_model": getattr(t, "vehicle_model", None),
        # Violation window (auto-filled, inspector-editable)
        "violation_start_at": t.violation_start_at.isoformat() if getattr(t, "violation_start_at", None) else None,
        "violation_end_at": t.violation_end_at.isoformat() if getattr(t, "violation_end_at", None) else None,
        "violation_started_at": t.violation_start_at.isoformat() if getattr(t, "violation_start_at", None) else None,
        "violation_ended_at": t.violation_end_at.isoformat() if getattr(t, "violation_end_at", None) else None,
        # Inspector approval
        "approved_by_inspector_id": getattr(t, "approved_by_inspector_id", None),
        "assigned_inspector_id": getattr(t, "assigned_inspector_id", None),
        "inspector_approved_at": t.inspector_approved_at.isoformat() if getattr(t, "inspector_approved_at", None) else None,
        "inspector_violation_rule_id": getattr(t, "inspector_violation_rule_id", None),
        "inspector_plate": getattr(t, "inspector_plate", None),
        # Extended review / snapshot layer
        "review_status": getattr(t, "review_status", None),
        "inspector_decision": getattr(t, "inspector_decision", None),
        "violation_duration_seconds": getattr(t, "violation_duration_seconds", None),
        "suspected_vehicle_marker_state": getattr(t, "suspected_vehicle_marker_state", None),
        "inspector_vehicle_color": getattr(t, "inspector_vehicle_color", None),
        "inspector_vehicle_type": getattr(t, "inspector_vehicle_type", None),
        "inspector_vehicle_make": getattr(t, "inspector_vehicle_make", None),
        "inspector_vehicle_model": getattr(t, "inspector_vehicle_model", None),
        "vehicle_registry_lookup_status": getattr(t, "vehicle_registry_lookup_status", None),
        "vehicle_registry_checked_at": t.vehicle_registry_checked_at.isoformat() if getattr(t, "vehicle_registry_checked_at", None) else None,
        "start_violation_screenshot_id": getattr(t, "start_violation_screenshot_id", None),
        "end_violation_screenshot_id": getattr(t, "end_violation_screenshot_id", None),
        "clear_plate_screenshot_id": getattr(t, "clear_plate_screenshot_id", None),
        "violation_context_screenshot_id": getattr(t, "violation_context_screenshot_id", None),
        "require_evidence_images": _require_evidence_images(),
    }



@router.get("/{ticket_id}/detail")
def get_ticket_detail(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    d = _ticket_dict(ticket)
    # Immutable snapshots + evidence-integrity hashes (rule 8). Detail-only so list payloads stay
    # lean; review/export read the frozen config from here, not live tables.
    d.update({
        "camera_id": getattr(ticket, "camera_id", None),
        "camera_section_id": getattr(ticket, "camera_section_id", None),
        "duplicate_of_ticket_id": getattr(ticket, "duplicate_of_ticket_id", None),
        "suspected_vehicle_track_id": getattr(ticket, "suspected_vehicle_track_id", None),
        "suspected_vehicle_box": getattr(ticket, "suspected_vehicle_box", None),
        "plate_box": getattr(ticket, "plate_box", None),
        "camera_config_snapshot": getattr(ticket, "camera_config_snapshot", None),
        "camera_section_snapshot": getattr(ticket, "camera_section_snapshot", None),
        "violation_rule_snapshot": getattr(ticket, "violation_rule_snapshot", None),
        "system_config_snapshot": getattr(ticket, "system_config_snapshot", None),
        "original_video_sha256": getattr(ticket, "original_video_sha256", None),
        "evidence_video_sha256": getattr(ticket, "evidence_video_sha256", None),
        "best_frame_sha256": getattr(ticket, "best_frame_sha256", None),
    })
    return d


def _is_processed_path(video_path: Optional[str]) -> bool:
    if not video_path:
        return False
    p = str(video_path).replace("\\", "/").lower()
    return p.startswith("processed/") or "/processed/" in f"/{p}" or "_processed" in p


def _normalize_blur_kernel_size(value: Optional[int]) -> int:
    k = int(value or 15)
    if k < 3:
        k = 15
    if k % 2 == 0:
        k += 1
    return k


def _get_blur_kernel_size(db) -> int:
    cfg = db.query(AppConfig).first()
    if not cfg:
        return 15
    return _normalize_blur_kernel_size(getattr(cfg, "blur_kernel_size", 15))


def _read_upload_job_raw_video_bytes(ticket, upload_job_repo: Optional[UploadJobRepository]) -> Optional[bytes]:
    if not upload_job_repo:
        return None

    upload_job_id = getattr(ticket, "upload_job_id", None)
    if not upload_job_id:
        return None

    try:
        job = upload_job_repo.get(upload_job_id)
    except Exception:
        return None

    if not job:
        return None

    raw_path = (
        getattr(job, "raw_video_path", None)
        or getattr(job, "video_path", None)
        or getattr(job, "file_path", None)
    )
    if not raw_path:
        return None

    fp = Path(settings.videos_dir) / str(raw_path).replace("\\", "/")
    if fp.exists():
        return fp.read_bytes()

    return None


def _build_processed_video_bytes(
    ticket,
    blur_strength: int,
    video_repo: CameraVideoRepository,
    upload_job_repo: Optional[UploadJobRepository],
) -> bytes:
    processed_video_id = getattr(ticket, "processed_video_id", None)
    if processed_video_id:
        vid = video_repo.get(processed_video_id)
        if vid and getattr(vid, "data", None):
            return bytes(vid.data)

    upload_job_bytes = _read_upload_job_raw_video_bytes(ticket, upload_job_repo)
    if upload_job_bytes:
        processed_bytes, _ = process_video(upload_job_bytes, blur_strength=blur_strength)
        return processed_bytes

    video_path = getattr(ticket, "video_path", None)
    if _is_processed_path(video_path):
        fp = Path(settings.videos_dir) / str(video_path).replace("\\", "/")
        if fp.exists():
            return fp.read_bytes()

    raw_video_id = getattr(ticket, "video_id", None)
    if raw_video_id:
        raw_vid = video_repo.get(raw_video_id)
        if raw_vid and getattr(raw_vid, "data", None):
            processed_bytes, _ = process_video(bytes(raw_vid.data), blur_strength=blur_strength)
            return processed_bytes

    raise HTTPException(status_code=404, detail="No source video available for processing")


@router.get("/{ticket_id}/video")
def get_ticket_video(
    ticket_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    upload_job_repo: Optional[UploadJobRepository] = Depends(get_upload_job_repo),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    blur = _get_blur_kernel_size(db)

    try:
        data = _build_processed_video_bytes(
            ticket,
            blur_strength=blur,
            video_repo=video_repo,
            upload_job_repo=upload_job_repo,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Processed video build failed for ticket %s", ticket_id)
        raise HTTPException(status_code=500, detail=f"Processed video build failed: {exc}")

    return Response(
        content=data,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/{ticket_id}/processed-video")
def get_ticket_processed_video(
    ticket_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    upload_job_repo: Optional[UploadJobRepository] = Depends(get_upload_job_repo),
):
    return get_ticket_video(
        ticket_id=ticket_id,
        db=db,
        ticket_repo=ticket_repo,
        video_repo=video_repo,
        upload_job_repo=upload_job_repo,
    )


@router.get("/{ticket_id}/raw-video")
def get_ticket_raw_video(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    raw_video_id = getattr(ticket, "video_id", None)
    if not raw_video_id:
        raise HTTPException(status_code=404, detail="No raw video attached")

    raw_vid = video_repo.get(raw_video_id)
    if not raw_vid or not getattr(raw_vid, "data", None):
        raise HTTPException(status_code=404, detail="Raw video not found")

    return Response(content=bytes(raw_vid.data), media_type="video/mp4")


@router.get("/{ticket_id}/original-video")
def get_ticket_original_video(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    original_path = getattr(ticket, "original_video_path", None)
    if not original_path:
        raise HTTPException(status_code=404, detail="No original video preserved for this ticket")

    fp = Path(settings.videos_dir) / str(original_path).replace("\\", "/")
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Original video file not found on disk")

    return Response(content=fp.read_bytes(), media_type="video/mp4")


@router.post("/{ticket_id}/reprocess-video")
def reprocess_ticket_video(
    ticket_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    video_repo: CameraVideoRepository = Depends(get_camera_video_repo),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    raw_video_id = getattr(ticket, "video_id", None)
    if not raw_video_id:
        raise HTTPException(status_code=404, detail="No raw video attached")

    raw_vid = video_repo.get(raw_video_id)
    if not raw_vid or not getattr(raw_vid, "data", None):
        raise HTTPException(status_code=404, detail="Raw video not found")

    blur = _get_blur_kernel_size(db)
    processed_bytes, preview_jpeg = process_video(bytes(raw_vid.data), blur_strength=blur)

    processed_dir = Path(settings.videos_dir) / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    processed_rel_path = f"processed/ticket_{ticket_id}.mp4"
    processed_abs_path = Path(settings.videos_dir) / processed_rel_path
    processed_abs_path.write_bytes(processed_bytes)

    ticket_image_path = None
    if preview_jpeg:
        ticket_image_rel = f"processed/ticket_{ticket_id}.jpg"
        (Path(settings.videos_dir) / ticket_image_rel).write_bytes(preview_jpeg)
        ticket_image_path = ticket_image_rel

    update_fields = {"video_path": processed_rel_path}
    if ticket_image_path:
        update_fields["ticket_image_path"] = ticket_image_path

    try:
        ticket_repo.update(ticket_id, **update_fields)
    except TypeError:
        ticket_repo.update(ticket_id, video_path=processed_rel_path)

    return {"ok": True, "message": "Video reprocessed with blur", "video_path": processed_rel_path}

@router.get("")
def list_tickets(
    status: Optional[str] = None,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    """Authenticated ticket list. One implementation only; includes review/workflow fields."""
    all_tickets = ticket_repo.list_all()
    if status:
        all_tickets = [t for t in all_tickets if t.status == status or getattr(t, "review_status", None) == status]
    return [_ticket_dict(t) for t in all_tickets]



@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: dict,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    """Update ticket status, fine, admin notes, or license plate. Used for approve/reject/edit."""
    from datetime import datetime, timezone
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    allowed = {"status", "fine_amount", "admin_notes", "license_plate", "description", "violation_zone"}
    update_kw = {k: v for k, v in payload.items() if k in allowed}
    _old_status = ticket.status

    if "status" in update_kw and update_kw["status"] in ("approved", "rejected"):
        update_kw["reviewed_at"] = datetime.now(timezone.utc)

    # #7 — admin approval must clear the same 4-evidence-image gate as inspector approval (the
    # generic PATCH previously bypassed every check).
    if update_kw.get("status") == "approved" and _require_evidence_images():
        from app.services.inspector_review_service import _resolve_evidence_screenshots
        from app.services.ticket_workflow_service import validate_ticket_before_approval
        _resolve_evidence_screenshots(db, ticket)
        db.commit()
        validate_ticket_before_approval(ticket)   # raises 400 if any of the 4 images is missing

    try:
        ticket_repo.update(ticket_id, **update_kw)
    except TypeError:
        for k, v in update_kw.items():
            setattr(ticket, k, v)
        db.commit()

    # #12 — audit admin approve/reject via the generic PATCH (inspector paths audit separately).
    if update_kw.get("status") in ("approved", "rejected"):
        try:
            from app.services.audit_log_service import write_ticket_audit
            write_ticket_audit(db, ticket_id=ticket_id, action_type=f"admin_{update_kw['status']}",
                               old_value={"status": _old_status}, new_value={"status": update_kw["status"]})
        except Exception:
            pass

    ticket = ticket_repo.get(ticket_id)
    return _ticket_dict(ticket)


class InspectorApprovalBody(BaseModel):
    inspector_plate: str                                   # vehicle number typed by the inspector
    inspector_violation_rule_id: Optional[str] = None      # chosen from the violation-types list
    violation_start_at: Optional[datetime] = None
    violation_end_at: Optional[datetime] = None
    vehicle_color: Optional[str] = None                    # inspector-entered (#7.3)
    vehicle_type: Optional[str] = None                     # inspector-entered (#7.3)
    admin_notes: Optional[str] = None
    fine_amount: Optional[int] = None


@router.patch("/{ticket_id}/approve")
def approve_ticket_as_inspector(
    ticket_id: int,
    body: InspectorApprovalBody,
    request: Request,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    inspector=Depends(get_current_inspector),
):
    """Inspector approval — thin router: delegates to inspector_review_service (validate plate 7/8
    digits, registry lookup + snapshot, 4-image gate, audit-log), then re-renders the video with the
    red 'approved' box (#10)."""
    from app.services.inspector_review_service import update_ticket_by_inspector

    current_ticket = ticket_repo.get(ticket_id)
    if not current_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_ticket.assigned_inspector_id not in (None, inspector.id):
        raise HTTPException(status_code=403, detail="הדוח משויך לפקח אחר.")

    ip = request.client.host if request.client else None
    ticket = update_ticket_by_inspector(
        ticket_repo.db,
        ticket_id=ticket_id,
        inspector_id=inspector.id,
        data={
            "plate_number": body.inspector_plate,
            "violation_rule_id": body.inspector_violation_rule_id,
            "vehicle_color": body.vehicle_color,
            "vehicle_type": body.vehicle_type,
            "violation_start_at": body.violation_start_at,
            "violation_end_at": body.violation_end_at,
            "fine_amount": body.fine_amount,
            "admin_notes": body.admin_notes,
            "approve": True,
        },
        ip_address=ip,
    )

    # #10 — the subject-car box turns red once the report is approved.
    try:
        from app.services.video_rerender import rerender_ticket_video
        from app.plate_pipeline.config import hex_to_bgr
        _cfg = ticket_repo.db.query(AppConfig).first()
        _approved = hex_to_bgr(getattr(_cfg, "approved_frame_color", "#FF0000"), (0, 0, 255)) if _cfg else (0, 0, 255)
        rerender_ticket_video(ticket_repo.db, ticket, box_color=_approved,
                              plate_override=ticket.inspector_plate or ticket.license_plate)
    except Exception as _rr:
        logging.getLogger(__name__).warning("approve re-render (red box) failed for ticket %s: %s", ticket_id, _rr)

    return _ticket_dict(ticket_repo.get(ticket_id))


class InspectorRejectionBody(BaseModel):
    rejection_reason: str
    notes: Optional[str] = None


@router.patch("/{ticket_id}/reject")
def reject_ticket_as_inspector(
    ticket_id: int,
    body: InspectorRejectionBody,
    request: Request,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    inspector=Depends(get_current_inspector),
):
    """Reject a ticket with a mandatory reason and immutable audit entry."""
    from app.services.inspector_review_service import update_ticket_by_inspector

    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_inspector_id not in (None, inspector.id):
        raise HTTPException(status_code=403, detail="הדוח משויך לפקח אחר.")

    updated = update_ticket_by_inspector(
        ticket_repo.db,
        ticket_id=ticket_id,
        inspector_id=inspector.id,
        data={
            "reject": True,
            "rejection_reason": body.rejection_reason,
            "notes": body.notes,
        },
        ip_address=request.client.host if request.client else None,
    )
    return _ticket_dict(updated)


@router.get("/inbox")
def inspector_inbox(
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    inspector=Depends(get_current_inspector),
):
    """Reports currently in the signed-in inspector's inbox (assigned to them) — #9."""
    rows = [
        t for t in ticket_repo.list_all()
        if getattr(t, "assigned_inspector_id", None) == inspector.id
        and getattr(t, "status", None) not in {"approved", "rejected", "final"}
    ]
    rows.sort(key=lambda t: getattr(t, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return [_ticket_dict(t) for t in rows]


class TransferBody(BaseModel):
    to_inspector_id: int
    reason: Optional[str] = None


@router.patch("/{ticket_id}/transfer")
def transfer_ticket(
    ticket_id: int,
    body: TransferBody,
    request: Request,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    inspector=Depends(get_current_inspector),
):
    """Transfer a report to another inspector's inbox (#9). Audited (rule 7)."""
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.assigned_inspector_id not in (None, inspector.id):
        raise HTTPException(status_code=403, detail="הדוח משויך לפקח אחר.")
    from app.models import Inspector
    target = (
        ticket_repo.db.query(Inspector)
        .filter(Inspector.id == body.to_inspector_id, Inspector.is_active.is_(True))
        .first()
    )
    if not target:
        raise HTTPException(status_code=400, detail="פקח היעד אינו קיים או אינו פעיל.")
    if target.id == inspector.id:
        raise HTTPException(status_code=400, detail="הדוח כבר נמצא בתיבת הפקח הנוכחי.")
    old_assignee = ticket.assigned_inspector_id
    ticket_repo.update(ticket_id, assigned_inspector_id=body.to_inspector_id)
    try:
        from app.services.audit_log_service import write_ticket_audit
        write_ticket_audit(
            ticket_repo.db, ticket_id=ticket_id, inspector_id=inspector.id, action_type="inspector_transfer",
            old_value={"assigned_inspector_id": old_assignee},
            new_value={"assigned_inspector_id": body.to_inspector_id},
            notes=body.reason,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        pass
    return _ticket_dict(ticket_repo.get(ticket_id))


class AssignBody(BaseModel):
    inspector_id: Optional[int] = None   # None → unassign (back to the unrouted pool)
    reason: Optional[str] = None


@router.patch("/{ticket_id}/assign")
def assign_ticket(
    ticket_id: int,
    body: AssignBody,
    request: Request,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    """Assign (or reassign / unassign) a ticket to an inspector's inbox — admin routing (#9). Only
    active inspectors may receive tickets. Every change is written to the immutable audit log."""
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    from app.models import Inspector
    if body.inspector_id is not None:
        target = (
            ticket_repo.db.query(Inspector)
            .filter(Inspector.id == body.inspector_id, Inspector.is_active.is_(True))
            .first()
        )
        if not target:
            raise HTTPException(status_code=400, detail="פקח היעד אינו קיים או אינו פעיל.")
    old_assignee = ticket.assigned_inspector_id
    ticket_repo.update(ticket_id, assigned_inspector_id=body.inspector_id)
    try:
        from app.services.audit_log_service import write_ticket_audit
        write_ticket_audit(
            ticket_repo.db, ticket_id=ticket_id, action_type="assign",
            old_value={"assigned_inspector_id": old_assignee},
            new_value={"assigned_inspector_id": body.inspector_id},
            notes=body.reason,
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        pass
    return _ticket_dict(ticket_repo.get(ticket_id))


@router.get("/{ticket_id}/audit")
def ticket_audit_log(
    ticket_id: int,
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """Audit trail for a ticket — every inspector action (rule 7)."""
    from app.models import TicketAuditLog
    rows = (
        db.query(TicketAuditLog)
        .filter(TicketAuditLog.ticket_id == ticket_id)
        .order_by(TicketAuditLog.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "action_type": r.action_type,
            "inspector_id": r.inspector_id,
            "old_value": r.old_value_json,
            "new_value": r.new_value_json,
            "notes": r.notes,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/{ticket_id}/screenshots")
def list_screenshots(
    ticket_id: int,
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    from sqlalchemy import text as _text
    rows = db.execute(
        _text("SELECT id, storage_path, frame_time_sec, frame_timestamp_ms, created_at FROM ticket_screenshots WHERE ticket_id = :tid ORDER BY id"),
        {"tid": ticket_id},
    ).fetchall()

    result = []
    for r in rows:
        frame_sec = r[2] if r[2] is not None else (r[3] / 1000.0 if r[3] is not None else None)
        result.append({
            "id": r[0],
            "storage_path": r[1],
            "frame_time_seconds": frame_sec,
            "created_at": r[4].isoformat() if r[4] else None,
        })
    return result


@router.get("/{ticket_id}/screenshots/{screenshot_id}/image")
def get_screenshot_image(
    ticket_id: int,
    screenshot_id: int,
    db=Depends(get_db),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    ticket = ticket_repo.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    from sqlalchemy import text as _text
    row = db.execute(
        _text("SELECT storage_path FROM ticket_screenshots WHERE id = :sid AND ticket_id = :tid"),
        {"sid": screenshot_id, "tid": ticket_id},
    ).fetchone()

    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    fp = Path(settings.videos_dir) / str(row[0]).replace("\\", "/")
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Screenshot file missing")

    return Response(content=fp.read_bytes(), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=86400"})
