"""Auth: unified login for admins and inspectors (פקחים)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import create_access_token, verify_password
from app.dependencies import get_admin_repo, get_inspector_repo
from app.repositories import AdminRepository
from app.repositories.inspector_repo import InspectorRepository

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_type: str = "admin"          # "admin" | "inspector"
    full_name: Optional[str] = None


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    admin_repo: AdminRepository = Depends(get_admin_repo),
    inspector_repo: InspectorRepository = Depends(get_inspector_repo),
):
    """Login as an admin or an inspector. The token carries the user type."""
    admin = admin_repo.get_by_username(data.username)
    if admin and verify_password(data.password, admin.hashed_password):
        return LoginResponse(
            access_token=create_access_token({"sub": admin.username, "type": "admin"}),
            username=admin.username,
            user_type="admin",
        )
    insp = inspector_repo.get_by_username(data.username)
    if insp and insp.is_active and verify_password(data.password, insp.hashed_password):
        return LoginResponse(
            access_token=create_access_token({"sub": insp.username, "type": "inspector"}),
            username=insp.username,
            user_type="inspector",
            full_name=insp.full_name,
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
    )
