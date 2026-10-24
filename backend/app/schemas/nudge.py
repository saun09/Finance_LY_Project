from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NudgeBriefingOut(BaseModel):
    briefing: str


class NudgeSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)
    # the conversation in progress, so its own lines aren't "recalled" back
    conversation_id: str | None = None


class NudgeSearchHitOut(BaseModel):
    topic: str
    text: str
    score: float


class NudgeSearchOut(BaseModel):
    # plain text, ready to hand straight back to the voice agent as the
    # client tool's result
    result_text: str
    hits: list[NudgeSearchHitOut]


class NudgeConversationIn(BaseModel):
    surface: str = Field(min_length=1, max_length=32)
    elevenlabs_conversation_id: str | None = None


class NudgeConversationEndIn(BaseModel):
    elevenlabs_conversation_id: str | None = None


class NudgeMessageIn(BaseModel):
    role: Literal["user", "agent"]
    text: str = Field(min_length=1)


class NudgeMessageOut(BaseModel):
    id: str
    role: str
    text: str
    created_at: datetime


class NudgeConversationOut(BaseModel):
    id: str
    surface: str
    elevenlabs_conversation_id: str | None
    started_at: datetime
    ended_at: datetime | None


class NudgeConversationSummaryOut(NudgeConversationOut):
    message_count: int
    preview: str | None


class NudgeConversationDetailOut(NudgeConversationOut):
    messages: list[NudgeMessageOut]
