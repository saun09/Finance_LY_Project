from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.nudge import (
    NudgeBriefingOut,
    NudgeConversationDetailOut,
    NudgeConversationEndIn,
    NudgeConversationIn,
    NudgeConversationOut,
    NudgeConversationSummaryOut,
    NudgeMessageIn,
    NudgeMessageOut,
    NudgeSearchHitOut,
    NudgeSearchIn,
    NudgeSearchOut,
)
from app.services.nudge_knowledge import build_session_briefing, format_search_results, list_messages, search_user_knowledge
from app.services.nudge_service import (
    ConversationNotFoundError,
    append_message,
    end_conversation,
    get_conversation,
    list_conversations,
    start_conversation,
)

router = APIRouter(prefix="/users/{user_id}/nudge", tags=["nudge"])


def _conversation_out(conv) -> NudgeConversationOut:
    return NudgeConversationOut(
        id=conv.id,
        surface=conv.surface,
        elevenlabs_conversation_id=conv.elevenlabs_conversation_id,
        started_at=conv.started_at,
        ended_at=conv.ended_at,
    )


def _message_out(msg) -> NudgeMessageOut:
    return NudgeMessageOut(id=msg.id, role=msg.role, text=msg.text, created_at=msg.created_at)


@router.get("/briefing", response_model=NudgeBriefingOut)
def get_briefing(user_id: str, surface: str = "home", conversation_id: str | None = None, session: Session = Depends(get_session)):
    return NudgeBriefingOut(briefing=build_session_briefing(session, user_id, surface, exclude_conversation_id=conversation_id))


@router.post("/search", response_model=NudgeSearchOut)
def post_search(user_id: str, body: NudgeSearchIn, session: Session = Depends(get_session)):
    results = search_user_knowledge(session, user_id, body.query, k=body.top_k, exclude_conversation_id=body.conversation_id)
    return NudgeSearchOut(
        result_text=format_search_results(results),
        hits=[NudgeSearchHitOut(topic=r.chunk.topic, text=r.chunk.text, score=r.score) for r in results],
    )


@router.post("/conversations", response_model=NudgeConversationOut, status_code=201)
def post_conversation(user_id: str, body: NudgeConversationIn, session: Session = Depends(get_session)):
    conv = start_conversation(
        session, user_id=user_id, surface=body.surface, elevenlabs_conversation_id=body.elevenlabs_conversation_id
    )
    return _conversation_out(conv)


@router.get("/conversations", response_model=list[NudgeConversationSummaryOut])
def get_conversations(user_id: str, session: Session = Depends(get_session)):
    return [
        NudgeConversationSummaryOut(**_conversation_out(conv).model_dump(), message_count=count, preview=preview)
        for conv, count, preview in list_conversations(session, user_id)
    ]


@router.get("/conversations/{conversation_id}", response_model=NudgeConversationDetailOut)
def get_conversation_detail(user_id: str, conversation_id: str, session: Session = Depends(get_session)):
    try:
        conv = get_conversation(session, user_id=user_id, conversation_id=conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NudgeConversationDetailOut(
        **_conversation_out(conv).model_dump(),
        messages=[_message_out(m) for m in list_messages(session, conv.id)],
    )


@router.post("/conversations/{conversation_id}/messages", response_model=NudgeMessageOut, status_code=201)
def post_message(user_id: str, conversation_id: str, body: NudgeMessageIn, session: Session = Depends(get_session)):
    try:
        msg = append_message(session, user_id=user_id, conversation_id=conversation_id, role=body.role, text=body.text)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _message_out(msg)


@router.post("/conversations/{conversation_id}/end", response_model=NudgeConversationOut)
def post_end_conversation(user_id: str, conversation_id: str, body: NudgeConversationEndIn, session: Session = Depends(get_session)):
    try:
        conv = end_conversation(
            session, user_id=user_id, conversation_id=conversation_id, elevenlabs_conversation_id=body.elevenlabs_conversation_id
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _conversation_out(conv)
