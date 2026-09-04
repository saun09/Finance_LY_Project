"""Real signup/login accounts. Independent of `user_profile` (which is
Module 2's onboarding data, created only once a signed-up user completes
onboarding) -- `AuthUser.user_id` is generated at signup and is the same
`user_id` string the rest of the app already keys everything on.

Scope note: this adds real password-checked account creation/sign-in --
signup and login genuinely fail on a wrong password. It does not retrofit
bearer-token authorization onto the rest of the API, which (by the
project's existing, documented design) trusts whatever `user_id` appears
in the URL path. Adding that would mean touching every existing route.
The frontend gates entry into the app on a successful login/signup and
remembers the resulting user_id locally, the same way the app already
persisted a plain demo user_id before this.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthUser(Base):
    __tablename__ = "auth_user"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
