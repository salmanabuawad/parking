"""Inspectors (פקחים) CRUD — managed by admins. Inspectors log in and approve reports."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, hash_password
from app.dependencies import get_inspector_repo
from app.models import Inspector
from app.repositories.inspector_repo import InspectorRepository
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
