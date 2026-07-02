"""Resolve the fields that go on a new ticket, given a read plate + the job/config (rule 6: keep
business logic in services, out of the worker). No file/HTTP I/O beyond the registry lookups.

Handles, in order:
  1. registry deep-check — confirm the read against the gov list, or correct a misread to a
     registered near-variant (image-grounded), with a human-readable note + suggestions;
  2. registry vehicle data (make/model/color) via the caller-supplied lookup;
  3. exemption — whitelisted plates become status='exempt' (recorded, not enforced);
  4. immutable config snapshots (rule 8);
  5. the violation window (start = capture time, end = start + clip length) and a
     'clip shorter than required' flag.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from sqlalchemy.orm import Session


def _clip_duration(video_params: Any) -> float | None:
    if isinstance(video_params, dict):
        for k in ("duration", "duration_sec", "duration_seconds"):
            if video_params.get(k):
                return float(video_params[k])
    return None


def resolve_ticket_fields(
    db: Session,
    *,
    job,
    cfg,
    display_plate: str,
    candidates,
    video_params,
    lookup_vehicle: Callable[[str, int], dict],
) -> dict[str, Any]:
    """Return the resolved ticket fields (plate may be corrected). Every step is non-fatal."""
    reason: str | None = None
    registry_status: str | None = None
    registry_raw: Any = None

    # 1) Registry deep-check — confirm the read, or correct a misread to a registered near-variant.
    if display_plate:
        try:
            from app.services.plate_registry_check import deep_check
            dc = deep_check(db, display_plate, candidates=candidates)
            registry_status = dc.get("status")
            registry_raw = dc.get("vehicle")
            if dc.get("corrected") and dc.get("plate"):
                print(f"[Job {job.id}] plate corrected via registry (OCR alt): {display_plate} -> {dc['plate']}", flush=True)
                reason = f"Auto-corrected {display_plate} -> {dc['plate']} (OCR alternative confirmed in gov registry)"
                display_plate = dc["plate"]
            elif registry_status == "not_in_registry":
                sug = dc.get("suggestions") or []
                if sug:
                    registry_raw = {"read": display_plate, "suggestions": sug}
                    hints = ", ".join(f"{s['plate']} ({s['make']})".strip() for s in sug)
                    reason = f"{display_plate} not in gov registry — possible matches: {hints}"
                else:
                    reason = f"{display_plate} not in gov registry — manual verification needed"
        except Exception as e:
            print(f"[Job {job.id}] registry deep-check failed (non-fatal): {e}", flush=True)

    vehicle_data = lookup_vehicle(display_plate, job.id) if display_plate else {}

    # 2) Exemption — whitelisted plates are recorded but not enforced.
    ticket_status = "pending_review"
    try:
        from app.services.vehicle_exemption_service import is_plate_exempt
        if display_plate and is_plate_exempt(db, display_plate):
            ticket_status = "exempt"
            reason = f"Exempt plate {display_plate} (whitelist) — no enforcement"
            print(f"[Job {job.id}] {display_plate} exempt — ticket marked exempt", flush=True)
    except Exception as e:
        print(f"[Job {job.id}] exemption check failed (non-fatal): {e}", flush=True)

    # 3) Immutable config snapshots (rule 8).
    try:
        from app.services.ticket_snapshot_service import build_ticket_snapshots
        snapshots = build_ticket_snapshots(db, camera_id=job.camera_id, section_id=None, rule_code=None)
    except Exception as e:
        print(f"[Job {job.id}] snapshot build failed (non-fatal): {e}", flush=True)
        snapshots = {}

    # 4) Violation window (inspector-editable) + required-length flag (system settings #1).
    req_secs = float(getattr(cfg, "required_video_seconds", 10) or 10) if cfg else 10.0
    actual_dur = _clip_duration(video_params)
    v_start = job.captured_at
    v_end = v_start + timedelta(seconds=(actual_dur if actual_dur is not None else req_secs)) if v_start is not None else None
    if actual_dur is not None and req_secs and actual_dur < req_secs:
        short = f"סרטון קצר מהנדרש: {actual_dur:.0f}ש׳ < {req_secs:.0f}ש׳"
        reason = f"{reason} · {short}" if reason else short

    return {
        "plate": display_plate,
        "vehicle_data": vehicle_data,
        "registry_status": registry_status,
        "registry_raw": registry_raw,
        "ticket_status": ticket_status,
        "review_status": "manual_review_required" if registry_status in ("corrected", "not_in_registry") else None,
        "snapshots": snapshots or {},
        "reason": reason,
        "v_start": v_start,
        "v_end": v_end,
    }
