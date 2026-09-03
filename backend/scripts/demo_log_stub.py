"""Stub call demonstrating how another module uses the event-log substrate.

Run with: python -m scripts.demo_log_stub  (from backend/)

Logs one fake suggestion event and one fake monthly snapshot against an
in-memory SQLite database, then reads both back to prove the round trip
works end to end.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

import app.models  # noqa: F401 — registers models on Base.metadata
from app.db import Base, make_engine
from app.models.suggestion_event import ActionTaken
from app.services.event_log import (
    get_user_event_history,
    get_user_snapshot_history,
    log_monthly_snapshot,
    log_suggestion_event,
    record_suggestion_outcome,
)


def main() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # A hypothetical debt_engine module shows a suggestion.
        event = log_suggestion_event(
            session,
            user_id="demo-user",
            module_source="debt_engine",
            tier="high_interest_debt",
            offset=0,
            suggested_value={"action": "pay_down_credit_card", "amount_paise": 500_000},
            market_context={"repo_rate_bps": 650, "as_of": "2026-09-03"},
        )
        print(f"logged suggestion_event {event.event_id}")

        # Later, the user edits the amount and follows through.
        record_suggestion_outcome(
            session,
            event_id=event.event_id,
            action_taken=ActionTaken.EDITED,
            chosen_value={"action": "pay_down_credit_card", "amount_paise": 300_000},
            delta={"amount_paise": -200_000},
            reason_code="wanted_to_keep_more_buffer",
            funded=True,
        )
        print("recorded outcome: edited + funded")

        # A hypothetical monthly job logs this user's snapshot.
        log_monthly_snapshot(
            session,
            user_id="demo-user",
            month=date(2026, 9, 1),
            income=80_000_00,
            surplus=15_000_00,
            cash=200_000_00,
            debt_to_income_ratio=Decimal("0.3500"),
            buffer_coverage_months=Decimal("2.50"),
        )
        print("logged monthly snapshot for 2026-09")

        events = get_user_event_history(session, "demo-user")
        snapshots = get_user_snapshot_history(session, "demo-user")

        print(f"read back {len(events)} event(s), {len(snapshots)} snapshot(s)")
        print(f"  event action_taken={events[0].action_taken}, funded={events[0].funded}")
        print(f"  snapshot buffer_coverage_months={snapshots[0].buffer_coverage_months}")


if __name__ == "__main__":
    main()
