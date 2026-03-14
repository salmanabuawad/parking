"""Auth: login."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import verify_password, create_access_token, get_current_user
from app.dependencies import get_admin_repo
from app.repositories import AdminRepository

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, admin_repo: AdminRepository = Depends(get_admin_repo)):
    """Login as admin. Returns JWT."""
    admin = admin_repo.get_by_username(data.username)
    if not admin or not verify_password(data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return LoginResponse(
        access_token=create_access_token({"sub": admin.username}),
        username=admin.username,
    )
