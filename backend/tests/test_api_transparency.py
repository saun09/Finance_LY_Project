import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-transparency-user-1"

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
            "cash_balance_paise": 800_000_00,
        },
    )
    client.post(
        f"/users/{USER}/holdings",
        json={"description": "Equity fund", "value_paise": 100_000_00, "holding_type": "equity_mutual_fund"},
    )
    client.post(f"/users/{USER}/risk-profile", json={"answers": AGGRESSIVE_ANSWERS})
    client.get(f"/users/{USER}/allocation")


def test_transparency_index_before_any_decision_is_empty(client):
    resp = client.get(f"/users/{USER}/transparency")
    assert resp.status_code == 200
    assert resp.json()["counts_by_module_source"] == {}


def test_unknown_module_source_is_404(client):
    resp = client.get(f"/users/{USER}/transparency/not_a_real_type")
    assert resp.status_code == 404


def test_risk_profile_trace_via_api(client):
    _onboard(client)
    resp = client.get(f"/users/{USER}/transparency/risk_profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["framing_label"] == "transparent reasoning"
    assert body["gap_detected"] is False
    assert body["reasoning"]["questionnaire"]["answers"] == AGGRESSIVE_ANSWERS


def test_allocation_trace_via_api_has_no_holding_descriptions(client):
    _onboard(client)
    resp = client.get(f"/users/{USER}/transparency/allocation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reasoning"]["which_rule"] == "v1"
    raw = resp.text
    assert "Equity fund" not in raw  # Module 4's hard constraint holds through the transparency view too


def test_index_reflects_computed_decisions(client):
    _onboard(client)
    resp = client.get(f"/users/{USER}/transparency")
    counts = resp.json()["counts_by_module_source"]
    assert counts.get("risk_profile", 0) >= 1
    assert counts.get("allocation", 0) >= 1
