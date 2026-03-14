"""Auth: password hashing, JWT, get_current_user."""
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.repositories import AdminRepository
from app.dependencies import get_admin_repo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


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
