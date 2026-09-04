"""Signup/login: real password verification gating account creation and
sign-in. See app/models/auth.py for what this does and doesn't cover.
"""

import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuthUser

MIN_PASSWORD_LENGTH = 8


class UsernameTakenError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class WeakPasswordError(ValueError):
    pass


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def signup(session: Session, username: str, password: str, commit: bool = True) -> AuthUser:
    username = username.strip()
    if not username:
        raise ValueError("username must not be blank")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

    existing = session.execute(select(AuthUser).where(AuthUser.username == username)).scalar_one_or_none()
    if existing is not None:
        raise UsernameTakenError(f"username {username!r} is already taken")

    user = AuthUser(user_id=str(uuid.uuid4()), username=username, password_hash=_hash_password(password))
    session.add(user)
    if commit:
        session.commit()
        session.refresh(user)
    else:
        session.flush()
    return user


def login(session: Session, username: str, password: str) -> AuthUser:
    username = username.strip()
    user = session.execute(select(AuthUser).where(AuthUser.username == username)).scalar_one_or_none()
    if user is None or not _verify_password(password, user.password_hash):
        raise InvalidCredentialsError("incorrect username or password")
    return user
