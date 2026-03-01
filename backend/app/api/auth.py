"""Auth API: signup/login/session/logout.

Uses JWT access tokens. For browser clients, we also set an HTTP-only cookie.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import db_session
from app.models.user import User, UserRole
from app.utils.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: UserRole


class AuthOut(BaseModel):
    user: UserOut
    token: str


def _get_db():
    with db_session() as s:
        yield s


@router.post("/signup", response_model=AuthOut)
async def signup(payload: SignupIn, response: Response, db: Session = Depends(_get_db)) -> AuthOut:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), role=UserRole.student)
    db.add(user)
    db.flush()  # assigns id

    token = create_access_token(subject=str(user.id), role=str(user.role.value))
    _set_auth_cookie(response, token)

    return AuthOut(user=UserOut(id=user.id, email=user.email, role=user.role), token=token)


@router.post("/login", response_model=AuthOut)
async def login(payload: LoginIn, response: Response, db: Session = Depends(_get_db)) -> AuthOut:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id), role=str(user.role.value))
    _set_auth_cookie(response, token)

    return AuthOut(user=UserOut(id=user.id, email=user.email, role=user.role), token=token)


@router.get("/session", response_model=AuthOut)
async def session(user: User = Depends(get_current_user)) -> AuthOut:
    token = create_access_token(subject=str(user.id), role=str(user.role.value))
    # We don't reset cookie on every call; client can use returned token for Bearer.
    return AuthOut(user=UserOut(id=user.id, email=user.email, role=user.role), token=token)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(settings.cookie_name)
    return {"ok": True}


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_exp_minutes * 60,
        path="/",
    )
