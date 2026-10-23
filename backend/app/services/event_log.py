"""Event-log substrate used by every suggestion-producing module.

Any module that shows the user a suggestion (risk profiling, allocation,
debt engine, leak engine, rumour verification, ...) must call
`log_suggestion_event` at the moment the suggestion is shown, and should
call `record_suggestion_outcome` later once the user has acted (or the
suggestion has gone stale/ignored). Snapshot-producing jobs call
`log_monthly_snapshot` once per user per month.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.models.user_monthly_snapshot import UserMonthlySnapshot

#: Marks an outcome field the caller did not pass, as distinct from an
#: explicit None ("set this to null"). See record_suggestion_outcome.
_UNSET: Any = object()


def log_suggestion_event(
    session: Session,
    *,
    user_id: str,
    module_source: str,
    suggested_value: dict,
    tier: str | None = None,
    offset: int | None = None,
    offset_pct_points: Decimal | None = None,
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
        offset_pct_points=offset_pct_points,
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


def _json_normalized(value: Any) -> Any:
    """What `value` looks like after a round trip through a JSON column
    (tuples become lists, etc.), so a freshly built suggested_value can be
    compared with one read back from the database."""
    return json.loads(json.dumps(value))


def log_suggestion_event_if_changed(
    session: Session,
    *,
    user_id: str,
    module_source: str,
    suggested_value: dict,
    compare_market_context: bool = False,
    **kwargs: Any,
) -> tuple[SuggestionEvent, bool]:
    """Log a suggestion only if it differs from what the user was last shown.

    Screens recompute their suggestion on every load. Logging each load
    would fill the event log with identical rows, so the "one row per
    suggestion shown" table would really be "one row per page view". This
    reuses the user's latest event for this module_source when its
    suggested_value is identical and nobody has responded to it yet. Once
    the user responds, the next load gets a fresh row, because a new
    response needs its own event to attach to.

    `compare_market_context=True` also requires market_context to match,
    for a module whose explanation can change while its headline value
    does not (Module 7's trace weights).

    Returns (event, created).
    """
    latest = get_user_event_history(session, user_id, module_source=module_source, limit=1)
    if (
        latest
        and latest[0].action_taken is None
        and latest[0].suggested_value == _json_normalized(suggested_value)
        and (
            not compare_market_context
            or latest[0].market_context == _json_normalized(kwargs.get("market_context") or {})
        )
    ):
        return latest[0], False

    event = log_suggestion_event(
        session, user_id=user_id, module_source=module_source, suggested_value=suggested_value, **kwargs
    )
    return event, True


def record_suggestion_outcome(
    session: Session,
    *,
    event_id: str,
    action_taken: ActionTaken | None = _UNSET,
    chosen_value: dict | None = _UNSET,
    delta: dict | None = _UNSET,
    reason_code: str | None = _UNSET,
    funded: bool | None = _UNSET,
    commit: bool = True,
) -> SuggestionEvent:
    """Update a previously logged event once the user has acted on it.

    Only the fields actually passed are written. A later, partial update
    (marking an earlier choice as funded, or contesting a decision from
    the transparency screen) must not wipe a chosen_value the user
    recorded earlier -- that row is training data.
    """
    event = session.get(SuggestionEvent, event_id)
    if event is None:
        raise ValueError(f"no suggestion_event with event_id={event_id!r}")

    if action_taken is not _UNSET:
        event.action_taken = action_taken
    if chosen_value is not _UNSET:
        event.chosen_value = chosen_value
    if delta is not _UNSET:
        event.delta = delta
    if reason_code is not _UNSET:
        event.reason_code = reason_code
    if funded is not _UNSET:
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


def count_events_by_module_source(
    session: Session,
    user_id: str,
    *,
    module_sources: tuple[str, ...] | None = None,
) -> dict[str, int]:
    """Exact event counts per module_source for one user, in one query.

    Counting by fetching rows and calling `len()` is both N queries and
    silently wrong past whatever fetch limit was used, which matters here
    because callers (Module 9's index) present the number to the user as
    "how many decisions of this kind you have". A grouped COUNT has
    neither problem. Sources with no events are simply absent from the
    result -- callers decide whether that means zero or "not applicable".
    """
    stmt = (
        select(SuggestionEvent.module_source, func.count())
        .where(SuggestionEvent.user_id == user_id)
        .group_by(SuggestionEvent.module_source)
    )
    if module_sources is not None:
        stmt = stmt.where(SuggestionEvent.module_source.in_(module_sources))
    return {source: count for source, count in session.execute(stmt).all()}


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
