from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SectionResultOut(BaseModel):
    """Per-section availability, so the UI can render three good blocks and
    one flagged-as-incomplete block instead of failing the whole trace."""

    key: str
    title: str
    available: bool
    missing_fields: tuple[str, ...]


class TraceResultOut(BaseModel):
    module_source: str
    display_name: str
    framing_label: str
    event_id: str
    timestamp: datetime
    headline: str
    reasoning: dict
    gap_detected: bool
    missing_fields: tuple[str, ...]
    sections: tuple[SectionResultOut, ...] = ()
    #: {leaf_key: unit} declared by the server, so the client never has to
    #: guess whether a raw integer is paise, a percentage or a count.
    value_hints: dict[str, str] = Field(default_factory=dict)
    value_hint_rules_version: str
    claim_note: str | None = None
    contested: bool = False
    contest_reason_code: str | None = None


class AvailableDecisionTypesOut(BaseModel):
    counts_by_module_source: dict[str, int]


class DecisionEventSummaryOut(BaseModel):
    event_id: str
    timestamp: datetime
    module_source: str
    display_name: str
    headline: str
    gap_detected: bool
    contested: bool


class FieldChangeOut(BaseModel):
    path: str
    before: Any = None
    after: Any = None
    hint: str | None = None


class TraceComparisonOut(BaseModel):
    module_source: str
    display_name: str
    framing_label: str
    before_event_id: str
    after_event_id: str
    before_timestamp: datetime
    after_timestamp: datetime
    before_headline: str
    after_headline: str
    changes: tuple[FieldChangeOut, ...]
    unchanged_field_count: int
    value_hints: dict[str, str] = Field(default_factory=dict)


class ContestDecisionIn(BaseModel):
    event_id: str
    reason_code: str
    note: str | None = Field(default=None, max_length=1000)
