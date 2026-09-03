from datetime import datetime

from pydantic import BaseModel


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


class AvailableDecisionTypesOut(BaseModel):
    counts_by_module_source: dict[str, int]
