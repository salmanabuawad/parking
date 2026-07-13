"""Inspectors (פקחים) CRUD — managed by admins. Inspectors log in and approve reports."""
from collections import Counter
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, hash_password
from app.dependencies import get_inspector_repo, get_ticket_repo
from app.models import Inspector
from app.repositories.inspector_repo import InspectorRepository
from app.repositories.ticket_repo import TicketRepository
from app.schemas import InspectorCreate, InspectorResponse, InspectorUpdate

router = APIRouter(prefix="/inspectors", tags=["inspectors"])


@router.get("", response_model=List[InspectorResponse])
def list_inspectors(
    active_only: bool = False,
    repo: InspectorRepository = Depends(get_inspector_repo),
    _=Depends(get_current_user),
):
    q = repo.db.query(Inspector)
    if active_only:
        q = q.filter(Inspector.is_active.is_(True))
    return q.order_by(Inspector.full_name).all()


@router.post("", response_model=InspectorResponse, status_code=status.HTTP_201_CREATED)
def create_inspector(
    data: InspectorCreate,
    repo: InspectorRepository = Depends(get_inspector_repo),
    _=Depends(get_current_user),
):
    if repo.get_by_username(data.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    return repo.create(
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        badge_number=data.badge_number,
        phone=data.phone,
        email=data.email,
        role=data.role,
        is_active=data.is_active,
    )


@router.patch("/{inspector_id}", response_model=InspectorResponse)
def update_inspector(
    inspector_id: int,
    data: InspectorUpdate,
    repo: InspectorRepository = Depends(get_inspector_repo),
    _=Depends(get_current_user),
):
    fields = data.model_dump(exclude_unset=True)
    pw = fields.pop("password", None)
    if pw:
        fields["hashed_password"] = hash_password(pw)
    insp = repo.update(inspector_id, **fields)
    if not insp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspector not found")
    return insp


@router.delete("/{inspector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inspector(
    inspector_id: int,
    repo: InspectorRepository = Depends(get_inspector_repo),
    _=Depends(get_current_user),
):
    if not repo.delete(inspector_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspector not found")


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _inbox_row(t) -> dict:
    return {
        "id": t.id,
        "license_plate": getattr(t, "license_plate", None),
        "status": getattr(t, "status", None),
        "review_status": getattr(t, "review_status", None),
        "location": getattr(t, "location", None),
        "violation_start_at": _iso(getattr(t, "violation_start_at", None)),
        "created_at": _iso(getattr(t, "created_at", None)),
    }


@router.get("/{inspector_id}/inbox")
def inspector_inbox_by_id(
    inspector_id: int,
    repo: InspectorRepository = Depends(get_inspector_repo),
    ticket_repo: TicketRepository = Depends(get_ticket_repo),
    _=Depends(get_current_user),
):
    """Inbox for a specific inspector (admin view, #9): open reports assigned to them + counts by
    status. Complements the self-scoped GET /api/tickets/inbox."""
    insp = repo.db.query(Inspector).filter(Inspector.id == inspector_id).first()
    if not insp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspector not found")
    rows = [t for t in ticket_repo.list_all() if getattr(t, "assigned_inspector_id", None) == inspector_id]
    counts = Counter(getattr(t, "status", None) or "unknown" for t in rows)
    closed = {"approved", "rejected", "final"}
    open_rows = [t for t in rows if getattr(t, "status", None) not in closed]
    open_rows.sort(key=lambda t: getattr(t, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return {
        "inspector_id": inspector_id,
        "inspector_name": insp.full_name,
        "is_active": insp.is_active,
        "status_counts": dict(counts),
        "open_count": len(open_rows),
        "tickets": [_inbox_row(t) for t in open_rows],
    }
