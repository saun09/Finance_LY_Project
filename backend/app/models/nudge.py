"""Stored Nudge (ElevenLabs voice assistant) conversations.

One `NudgeConversation` per voice session the user starts from the app,
and one `NudgeMessage` per finalized transcript line (user or agent) the
ElevenLabs SDK hands the client. The client posts each line as it arrives
rather than one batch at the end, so a crash or dropped connection mid-call
still leaves everything said up to that point on record.

`user_id` deliberately has no FK to `user_profile`: a freshly signed-up
user can talk to Nudge before finishing onboarding, and their conversation
should still be kept.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NudgeConversation(Base):
    __tablename__ = "nudge_conversation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    # which app screen the conversation was opened from (home/progress/...)
    surface: Mapped[str] = mapped_column(String(32), nullable=False)
    # ElevenLabs' own id for the session, so a stored conversation can be
    # matched against the agent dashboard's history; unknown until connected
    elevenlabs_conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NudgeMessage(Base):
    __tablename__ = "nudge_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("nudge_conversation.id"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "agent"
    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
