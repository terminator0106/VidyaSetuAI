"""Security utilities: password hashing + JWT auth dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
import hashlib

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Generator

from app.config import settings
from app.database import db_session
from app.models.user import User, UserRole


def _bcrypt_input(password: str) -> bytes:
    """Prepare password bytes for bcrypt.

    bcrypt only uses the first 72 bytes; for longer passwords, pre-hash with
    SHA-256 to preserve full entropy.
    """

    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return raw
    return hashlib.sha256(raw).digest()


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""

    hashed = bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored bcrypt hash."""

    try:
        return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token."""

    exp_minutes = expires_minutes if expires_minutes is not None else settings.access_token_exp_minutes
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT token."""

    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


def _get_db() -> Generator[Session, None, None]:
    with db_session() as s:
        yield s


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def get_current_user(
    request: Request,
    db: Session = Depends(_get_db),
    access_cookie: Optional[str] = Cookie(default=None, alias=settings.cookie_name),
) -> User:
    """FastAPI dependency that returns the authenticated user."""

    token = _extract_bearer_token(request) or access_cookie
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(sub)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to enforce admin role."""

    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
