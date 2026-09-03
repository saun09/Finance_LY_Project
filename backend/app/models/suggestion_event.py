import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActionTaken(str, enum.Enum):
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    IGNORED = "ignored"


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SuggestionEvent(Base):
    """One row per suggestion instance shown to a user by any module.

    `suggested_value` / `chosen_value` / `delta` are JSON because different
    modules suggest different shapes (a rupee amount, an asset-class
    allocation, a debt payoff order, ...). `delta` is deliberately JSON
    rather than a single number so a module can report a structured diff
    (e.g. {"amount_paise": -50000}) instead of losing information by
    collapsing it to one figure.
    """

    __tablename__ = "suggestion_event"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    # e.g. "risk_profile", "allocation", "debt_engine", "leak_engine"
    module_source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # module-defined tier label (e.g. a risk tier or suggestion priority tier)
    tier: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # position/sequence of this suggestion within the set shown for this
    # module_source + tier (module-defined semantics, e.g. rank in a list)
    offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    suggested_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    chosen_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    action_taken: Mapped[ActionTaken | None] = mapped_column(
        Enum(ActionTaken, name="action_taken_enum", native_enum=True), nullable=True
    )
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    funded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # snapshot of market context (e.g. index levels, reference rates) at
    # event time, so a later transparency view can explain "why this, then"
    market_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
