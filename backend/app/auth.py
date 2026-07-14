"""Auth: password hashing, JWT, get_current_user."""
from datetime import datetime, timedelta
import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.repositories import AdminRepository
from app.repositories.inspector_repo import InspectorRepository
from app.dependencies import get_admin_repo, get_inspector_repo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def _validate_token(token: str, admin_repo: AdminRepository):
    """Validate JWT and return admin user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = admin_repo.get_by_username(username)
    if not user:
        raise credentials_exception
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    admin_repo: AdminRepository = Depends(get_admin_repo),
):
    return _validate_token(token, admin_repo)


def get_current_user_for_media(
    request: Request,
    admin_repo: AdminRepository = Depends(get_admin_repo),
):
    """Auth for media endpoints: accepts Bearer header or ?token= query param (for video src)."""
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.query_params.get("token")
    return _validate_token(token, admin_repo)


def _validate_inspector_token(token: str, inspector_repo: InspectorRepository):
    """Validate a JWT and require it to be an active inspector's token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username or payload.get("type") != "inspector":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    insp = inspector_repo.get_by_username(username)
    if not insp or not insp.is_active:
        raise credentials_exception
    return insp


def get_current_inspector(
    token: str = Depends(oauth2_scheme),
    inspector_repo: InspectorRepository = Depends(get_inspector_repo),
):
    return _validate_inspector_token(token, inspector_repo)


class Reviewer:
    """A ticket reviewer: an inspector, or an admin acting as a 'super inspector'.

    `inspector_id` is None for admins so the inspector FK columns (approved_by_inspector_id,
    assigned_inspector_id, audit inspector_id — all nullable FKs to inspectors) stay null.
    """

    def __init__(self, kind: str, inspector_id, username: str):
        self.kind = kind                  # 'inspector' | 'admin'
        self.inspector_id = inspector_id  # int | None
        self.username = username


def get_current_reviewer(
    token: str = Depends(oauth2_scheme),
    admin_repo: AdminRepository = Depends(get_admin_repo),
    inspector_repo: InspectorRepository = Depends(get_inspector_repo),
) -> "Reviewer":
    """Accept an inspector OR admin token. Admins are 'super inspectors': they can review,
    capture evidence, and approve/reject tickets just like inspectors."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception
    username = payload.get("sub")
    if not username:
        raise credentials_exception
    if payload.get("type") == "inspector":
        insp = inspector_repo.get_by_username(username)
        if insp and insp.is_active:
            return Reviewer("inspector", insp.id, username)
    else:
        adm = admin_repo.get_by_username(username)
        if adm:
            return Reviewer("admin", None, username)
    raise credentials_exception
