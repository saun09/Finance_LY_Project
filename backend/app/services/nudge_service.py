"""Storage for Nudge voice conversations -- the only layer that writes the
nudge_conversation/nudge_message tables. Retrieval and the session
briefing live in app/services/nudge_knowledge.py."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.nudge import NudgeConversation, NudgeMessage
from app.services.nudge_knowledge import list_messages

VALID_ROLES = ("user", "agent")


class ConversationNotFoundError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def start_conversation(
    session: Session, *, user_id: str, surface: str, elevenlabs_conversation_id: str | None = None, commit: bool = True
) -> NudgeConversation:
    conv = NudgeConversation(user_id=user_id, surface=surface, elevenlabs_conversation_id=elevenlabs_conversation_id)
    session.add(conv)
    if commit:
        session.commit()
        session.refresh(conv)
    return conv


def get_conversation(session: Session, *, user_id: str, conversation_id: str) -> NudgeConversation:
    conv = session.get(NudgeConversation, conversation_id)
    # scoped to user_id so one user's conversation can't be read or
    # appended to through another user's URL
    if conv is None or conv.user_id != user_id:
        raise ConversationNotFoundError(f"no nudge conversation {conversation_id!r} for user_id={user_id!r}")
    return conv


def append_message(
    session: Session, *, user_id: str, conversation_id: str, role: str, text: str, commit: bool = True
) -> NudgeMessage:
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
    text = text.strip()
    if not text:
        raise ValueError("message text must not be empty")
    get_conversation(session, user_id=user_id, conversation_id=conversation_id)
    msg = NudgeMessage(conversation_id=conversation_id, role=role, text=text)
    session.add(msg)
    if commit:
        session.commit()
        session.refresh(msg)
    return msg


def end_conversation(
    session: Session, *, user_id: str, conversation_id: str, elevenlabs_conversation_id: str | None = None, commit: bool = True
) -> NudgeConversation:
    conv = get_conversation(session, user_id=user_id, conversation_id=conversation_id)
    if conv.ended_at is None:
        conv.ended_at = _utcnow()
    if elevenlabs_conversation_id and not conv.elevenlabs_conversation_id:
        conv.elevenlabs_conversation_id = elevenlabs_conversation_id
    if commit:
        session.commit()
        session.refresh(conv)
    return conv


def list_conversations(session: Session, user_id: str, limit: int = 50) -> list[tuple[NudgeConversation, int, str | None]]:
    """(conversation, message_count, first user message) per conversation,
    most recent first -- enough for a history list without loading every
    transcript."""
    convs = session.execute(
        select(NudgeConversation)
        .where(NudgeConversation.user_id == user_id)
        .order_by(NudgeConversation.started_at.desc())
        .limit(limit)
    ).scalars().all()
    counts = dict(
        session.execute(
            select(NudgeMessage.conversation_id, func.count())
            .where(NudgeMessage.conversation_id.in_([c.id for c in convs]))
            .group_by(NudgeMessage.conversation_id)
        ).all()
    )
    out = []
    for conv in convs:
        first_user = next((m.text for m in list_messages(session, conv.id) if m.role == "user"), None)
        out.append((conv, counts.get(conv.id, 0), first_user))
    return out
