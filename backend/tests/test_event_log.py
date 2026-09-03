from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.suggestion_event import ActionTaken
from app.services.event_log import (
    get_user_event_history,
    get_user_snapshot_history,
    log_monthly_snapshot,
    log_suggestion_event,
    record_suggestion_outcome,
)

USER = "user-1"


def test_log_suggestion_event_defaults_unacted(session):
    event = log_suggestion_event(
        session,
        user_id=USER,
        module_source="debt_engine",
        tier="high_interest",
        offset=0,
        suggested_value={"action": "pay_down_credit_card", "amount_paise": 500000},
        market_context={"repo_rate_bps": 650},
    )

    assert event.event_id
    assert event.chosen_value is None
    assert event.action_taken is None
    assert event.funded is None
    assert event.suggested_value["amount_paise"] == 500000
    assert event.market_context == {"repo_rate_bps": 650}


def test_record_suggestion_outcome_updates_row(session):
    event = log_suggestion_event(
        session,
        user_id=USER,
        module_source="leak_engine",
        suggested_value={"action": "cancel_subscription", "amount_paise": 39900},
    )

    updated = record_suggestion_outcome(
        session,
        event_id=event.event_id,
        action_taken=ActionTaken.EDITED,
        chosen_value={"action": "downgrade_subscription", "amount_paise": 19900},
        delta={"amount_paise": -20000},
        reason_code="still_uses_it",
        funded=True,
    )

    assert updated.event_id == event.event_id
    assert updated.action_taken == ActionTaken.EDITED
    assert updated.chosen_value["amount_paise"] == 19900
    assert updated.delta == {"amount_paise": -20000}
    assert updated.reason_code == "still_uses_it"
    assert updated.funded is True


def test_record_suggestion_outcome_missing_event_raises(session):
    with pytest.raises(ValueError):
        record_suggestion_outcome(
            session,
            event_id="does-not-exist",
            action_taken=ActionTaken.REJECTED,
        )


def test_get_user_event_history_filters_and_orders(session):
    old = log_suggestion_event(
        session,
        user_id=USER,
        module_source="allocation",
        suggested_value={"asset_class": "debt"},
        timestamp=datetime.now(timezone.utc) - timedelta(days=2),
    )
    new = log_suggestion_event(
        session,
        user_id=USER,
        module_source="allocation",
        suggested_value={"asset_class": "equity"},
    )
    log_suggestion_event(
        session,
        user_id=USER,
        module_source="debt_engine",
        suggested_value={"action": "pay_down"},
    )
    log_suggestion_event(
        session,
        user_id="someone-else",
        module_source="allocation",
        suggested_value={"asset_class": "cash"},
    )

    history = get_user_event_history(session, USER, module_source="allocation")

    assert [e.event_id for e in history] == [new.event_id, old.event_id]


def test_get_user_event_history_respects_limit_and_offset(session):
    for i in range(5):
        log_suggestion_event(
            session,
            user_id=USER,
            module_source="allocation",
            suggested_value={"i": i},
        )

    page1 = get_user_event_history(session, USER, limit=2, offset=0)
    page2 = get_user_event_history(session, USER, limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert {e.event_id for e in page1}.isdisjoint({e.event_id for e in page2})


def test_log_monthly_snapshot_inserts_then_upserts(session):
    month = date(2026, 8, 15)

    first = log_monthly_snapshot(
        session,
        user_id=USER,
        month=month,
        income=8_000_00,
        surplus=1_500_00,
        cash=20_000_00,
        debt_to_income_ratio=Decimal("0.3500"),
        buffer_coverage_months=Decimal("2.50"),
    )
    assert first.month == date(2026, 8, 1)

    second = log_monthly_snapshot(
        session,
        user_id=USER,
        month=month,
        income=8_200_00,
        surplus=1_700_00,
        cash=21_000_00,
        debt_to_income_ratio=Decimal("0.3300"),
        buffer_coverage_months=Decimal("2.70"),
    )

    assert second.snapshot_id == first.snapshot_id
    all_snapshots = get_user_snapshot_history(session, USER)
    assert len(all_snapshots) == 1
    assert all_snapshots[0].income == 8_200_00
    assert all_snapshots[0].debt_to_income_ratio == Decimal("0.3300")


def test_get_user_snapshot_history_orders_and_filters_by_month(session):
    for m in (date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)):
        log_monthly_snapshot(
            session,
            user_id=USER,
            month=m,
            income=1000,
            surplus=100,
            cash=5000,
            debt_to_income_ratio=Decimal("0.1000"),
            buffer_coverage_months=Decimal("1.00"),
        )

    history = get_user_snapshot_history(session, USER, since_month=date(2026, 7, 1))

    assert [s.month for s in history] == [date(2026, 8, 1), date(2026, 7, 1)]
