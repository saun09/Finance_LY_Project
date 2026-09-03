"""Event-log substrate used by every suggestion-producing module.

Any module that shows the user a suggestion (risk profiling, allocation,
debt engine, leak engine, rumour verification, ...) must call
`log_suggestion_event` at the moment the suggestion is shown, and should
call `record_suggestion_outcome` later once the user has acted (or the
suggestion has gone stale/ignored). Snapshot-producing jobs call
`log_monthly_snapshot` once per user per month.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.models.user_monthly_snapshot import UserMonthlySnapshot


def log_suggestion_event(
    session: Session,
    *,
    user_id: str,
    module_source: str,
    suggested_value: dict,
    tier: str | None = None,
    offset: int | None = None,
    chosen_value: dict | None = None,
    delta: dict | None = None,
    action_taken: ActionTaken | None = None,
    reason_code: str | None = None,
    funded: bool | None = None,
    market_context: dict | None = None,
    timestamp: datetime | None = None,
    commit: bool = True,
) -> SuggestionEvent:
    """Write one suggestion_event row and return it.

    Called at the moment a suggestion is shown to the user. `chosen_value`,
    `delta`, `action_taken`, `reason_code`, and `funded` are normally still
    unknown at that point and are left null; call
    `record_suggestion_outcome` once the user has responded.
    """
    event = SuggestionEvent(
        user_id=user_id,
        module_source=module_source,
        suggested_value=suggested_value,
        tier=tier,
        offset=offset,
        chosen_value=chosen_value,
        delta=delta,
        action_taken=action_taken,
        reason_code=reason_code,
        funded=funded,
        market_context=market_context or {},
    )
    if timestamp is not None:
        event.timestamp = timestamp

    session.add(event)
    if commit:
        session.commit()
        session.refresh(event)
    else:
        session.flush()
    return event


def record_suggestion_outcome(
    session: Session,
    *,
    event_id: str,
    action_taken: ActionTaken,
    chosen_value: dict | None = None,
    delta: dict | None = None,
    reason_code: str | None = None,
    funded: bool | None = None,
    commit: bool = True,
) -> SuggestionEvent:
    """Update a previously logged event once the user has acted on it."""
    event = session.get(SuggestionEvent, event_id)
    if event is None:
        raise ValueError(f"no suggestion_event with event_id={event_id!r}")

    event.action_taken = action_taken
    event.chosen_value = chosen_value
    event.delta = delta
    event.reason_code = reason_code
    event.funded = funded

    if commit:
        session.commit()
        session.refresh(event)
    else:
        session.flush()
    return event


def log_monthly_snapshot(
    session: Session,
    *,
    user_id: str,
    month: date,
    income: int,
    surplus: int,
    cash: int,
    debt_to_income_ratio: Decimal,
    buffer_coverage_months: Decimal,
    computed_at: datetime | None = None,
    commit: bool = True,
) -> UserMonthlySnapshot:
    """Write (or overwrite) the one snapshot row for this user and month.

    `month` should be the first day of the covered calendar month. If a
    snapshot for this user/month already exists (e.g. a recompute after
    correcting an input), it is updated in place rather than duplicated.
    """
    month = month.replace(day=1)

    existing = session.execute(
        select(UserMonthlySnapshot).where(
            UserMonthlySnapshot.user_id == user_id,
            UserMonthlySnapshot.month == month,
        )
    ).scalar_one_or_none()

    snapshot = existing or UserMonthlySnapshot(user_id=user_id, month=month)
    snapshot.income = income
    snapshot.surplus = surplus
    snapshot.cash = cash
    snapshot.debt_to_income_ratio = debt_to_income_ratio
    snapshot.buffer_coverage_months = buffer_coverage_months
    if computed_at is not None:
        snapshot.computed_at = computed_at

    if existing is None:
        session.add(snapshot)

    if commit:
        session.commit()
        session.refresh(snapshot)
    else:
        session.flush()
    return snapshot


def get_user_event_history(
    session: Session,
    user_id: str,
    *,
    module_source: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SuggestionEvent]:
    """Fetch a user's suggestion_event rows, most recent first."""
    stmt = select(SuggestionEvent).where(SuggestionEvent.user_id == user_id)
    if module_source is not None:
        stmt = stmt.where(SuggestionEvent.module_source == module_source)
    if since is not None:
        stmt = stmt.where(SuggestionEvent.timestamp >= since)
    if until is not None:
        stmt = stmt.where(SuggestionEvent.timestamp <= until)
    stmt = stmt.order_by(SuggestionEvent.timestamp.desc()).limit(limit).offset(offset)
    return list(session.execute(stmt).scalars().all())


def get_user_snapshot_history(
    session: Session,
    user_id: str,
    *,
    since_month: date | None = None,
    until_month: date | None = None,
    limit: int = 24,
) -> list[UserMonthlySnapshot]:
    """Fetch a user's monthly snapshots, most recent month first."""
    stmt = select(UserMonthlySnapshot).where(UserMonthlySnapshot.user_id == user_id)
    if since_month is not None:
        stmt = stmt.where(UserMonthlySnapshot.month >= since_month.replace(day=1))
    if until_month is not None:
        stmt = stmt.where(UserMonthlySnapshot.month <= until_month.replace(day=1))
    stmt = stmt.order_by(UserMonthlySnapshot.month.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())
