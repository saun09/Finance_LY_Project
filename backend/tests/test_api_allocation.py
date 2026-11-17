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
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
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


def test_setting_a_holding_type_afterward_unblocks_allocation(client):
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
    holding = client.post(f"/users/{USER}/holdings", json={"description": "Not sure what this is", "value_paise": 1000}).json()
    client.post(f"/users/{USER}/risk-profile", json={"answers": AGGRESSIVE_ANSWERS})
    assert client.get(f"/users/{USER}/allocation").status_code == 422

    resp = client.put(f"/users/{USER}/holdings/{holding['id']}/type", json={"holding_type": "fixed_deposit"})
    assert resp.status_code == 200
    assert resp.json()["holding_type"] == "fixed_deposit"

    assert client.get(f"/users/{USER}/allocation").status_code == 200


def test_setting_type_on_someone_elses_or_unknown_holding_is_404(client):
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
    resp = client.put(f"/users/{USER}/holdings/does-not-exist/type", json={"holding_type": "ppf"})
    assert resp.status_code == 404


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
