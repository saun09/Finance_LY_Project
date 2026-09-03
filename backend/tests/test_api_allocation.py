import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-alloc-user-1"

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
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
            "cash_balance_paise": 1_000_000_00,
        },
    )
    client.post(
        f"/users/{USER}/holdings",
        json={"description": "Equity fund holding", "value_paise": 100_000_00, "holding_type": "equity_mutual_fund"},
    )
    client.post(
        f"/users/{USER}/holdings",
        json={"description": "ULIP holding", "value_paise": 200_000_00, "holding_type": "ulip"},
    )


def test_allocation_without_risk_tier_is_409(client):
    _onboard(client)
    resp = client.get(f"/users/{USER}/allocation")
    assert resp.status_code == 409


def test_allocation_with_unclassified_holding_is_422(client):
    client.put(
        f"/users/{USER}/profile",
        json={
            "income_paise": 100_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 0,
            "cash_balance_paise": 1_000_000_00,
        },
    )
    client.post(f"/users/{USER}/holdings", json={"description": "Unclassified thing", "value_paise": 1000})
    client.post(f"/users/{USER}/risk-profile", json={"answers": AGGRESSIVE_ANSWERS})

    resp = client.get(f"/users/{USER}/allocation")
    assert resp.status_code == 422


def test_full_allocation_flow_via_api_shows_look_through(client):
    _onboard(client)
    client.post(f"/users/{USER}/risk-profile", json={"answers": AGGRESSIVE_ANSWERS})

    resp = client.get(f"/users/{USER}/allocation")
    assert resp.status_code == 200
    body = resp.json()

    assert body["final_tier"] == 5
    # equity = 100,000_00 (pure fund) + 100,000_00 (ULIP 50% of 200,000_00) = 200,000_00
    assert body["current_exposure_paise"]["equity"] == 200_000_00
    assert body["current_exposure_paise"]["debt"] == 100_000_00
    assert len(body["holdings"]) == 2
    for h in body["holdings"]:
        assert "description" not in h

    raw = resp.text
    assert "ULIP holding" not in raw
    assert "Equity fund holding" not in raw
