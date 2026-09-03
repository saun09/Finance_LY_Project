from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.suggestion_event import ActionTaken


class SuggestionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    user_id: str
    timestamp: datetime
    module_source: str
    tier: str | None
    offset: int | None
    suggested_value: dict
    chosen_value: dict | None
    delta: dict | None
    action_taken: ActionTaken | None
    reason_code: str | None
    funded: bool | None
    market_context: dict
    created_at: datetime
