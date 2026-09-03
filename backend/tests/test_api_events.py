from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.services.event_log import log_monthly_snapshot, log_suggestion_event

USER = "api-user-1"


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_read_user_events(session, client):
    log_suggestion_event(
        session,
        user_id=USER,
        module_source="debt_engine",
        suggested_value={"action": "pay_down_credit_card", "amount_paise": 500000},
    )

    resp = client.get(f"/users/{USER}/events")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["module_source"] == "debt_engine"
    assert body[0]["suggested_value"]["amount_paise"] == 500000


def test_read_user_snapshots(session, client):
    log_monthly_snapshot(
        session,
        user_id=USER,
        month=date(2026, 8, 1),
        income=8_000_00,
        surplus=1_500_00,
        cash=20_000_00,
        debt_to_income_ratio=Decimal("0.3500"),
        buffer_coverage_months=Decimal("2.50"),
    )

    resp = client.get(f"/users/{USER}/snapshots")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["income"] == 800000
