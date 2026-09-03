from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-personalization-user-1"

CONSERVATIVE_ANSWERS = {
    "horizon": "lt_1y",
    "drawdown_reaction": "sell_all",
    "experience": "none",
    "goal": "preserve",
}


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _onboard(client):
    client.put(
        f"/users/{USER}/profile",
        json={
            "income_paise": 100_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 0,
            "cash_balance_paise": 10_000_000_00,
        },
    )
    client.post(
        f"/users/{USER}/holdings",
        json={"description": "Equity fund", "value_paise": 100_000_00, "holding_type": "equity_mutual_fund"},
    )
    client.post(f"/users/{USER}/risk-profile", json={"answers": CONSERVATIVE_ANSWERS})
    return client.get(f"/users/{USER}/allocation").json()


def test_personalization_without_allocation_is_409(client):
    resp = client.get(f"/users/{USER}/personalization")
    assert resp.status_code == 409


def test_full_personalization_flow_via_api(client):
    _onboard(client)

    resp = client.get(f"/users/{USER}/personalization")
    assert resp.status_code == 200
    body = resp.json()
    assert body["offset_pct_points"] == "0"
    assert body["displayed_target_pct"]["equity"] == "10.00"

    events_resp = client.get(f"/users/{USER}/events?module_source=allocation")
    event_id = events_resp.json()[0]["event_id"]

    outcome_resp = client.post(
        f"/users/{USER}/allocation/{event_id}/outcome",
        json={
            "action_taken": "edited",
            "chosen_target_pct": {"cash": "5", "debt": "50", "equity": "25", "real_assets": "15", "alternatives": "5"},
            "funded": True,
        },
    )
    assert outcome_resp.status_code == 200

    resp2 = client.get(f"/users/{USER}/personalization")
    body2 = resp2.json()
    assert Decimal(body2["offset_pct_points"]) == Decimal("4.5")
    assert Decimal(body2["displayed_target_pct"]["equity"]) == Decimal("14.50")
    assert body2["edits_considered"] == 1
    assert len(body2["trace"]) == 1


def test_outcome_on_unknown_event_is_404(client):
    _onboard(client)
    resp = client.post(
        f"/users/{USER}/allocation/does-not-exist/outcome",
        json={"action_taken": "rejected"},
    )
    assert resp.status_code == 404
