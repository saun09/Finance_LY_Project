import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-risk-user-1"

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


def _onboard_core_scenario(client):
    client.put(
        f"/users/{USER}/profile",
        json={
            "income_paise": 100_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 0,
            "cash_balance_paise": 200_000_00,
        },
    )
    client.post(
        f"/users/{USER}/expenses",
        json={"category": "essentials", "amount_paise": 100_000_00, "frequency": "monthly", "is_essential": True},
    )
    client.post(
        f"/users/{USER}/emis",
        json={"lender": "Heavy Personal Loan Co", "amount_paise": 45_000_00, "remaining_tenure_months": 24, "annual_rate_bps": 1200},
    )


def test_risk_profile_endpoint_for_unknown_user_is_404(client):
    resp = client.post("/users/does-not-exist/risk-profile", json={"answers": AGGRESSIVE_ANSWERS})
    assert resp.status_code == 404


def test_core_scenario_via_api_caps_and_explains(client):
    _onboard_core_scenario(client)

    resp = client.post(f"/users/{USER}/risk-profile", json={"answers": AGGRESSIVE_ANSWERS})
    assert resp.status_code == 200
    body = resp.json()

    assert body["stated_tier"] == 5
    assert body["final_tier"] == 2
    assert body["capped"] is True
    assert body["binding_constraints"] == ["emi_to_income_ratio"]
    assert "Rs 25,000" in body["unlock_conditions"][0]["message"]

    latest = client.get(f"/users/{USER}/risk-profile/latest")
    assert latest.status_code == 200
    assert latest.json()["final_tier"] == 2


def test_missing_answer_via_api_is_422(client):
    _onboard_core_scenario(client)
    incomplete = dict(AGGRESSIVE_ANSWERS)
    del incomplete["goal"]
    resp = client.post(f"/users/{USER}/risk-profile", json={"answers": incomplete})
    assert resp.status_code == 422


def test_latest_before_any_computation_is_404(client):
    _onboard_core_scenario(client)
    resp = client.get(f"/users/{USER}/risk-profile/latest")
    assert resp.status_code == 404


def test_questionnaire_endpoint_is_not_user_scoped_and_omits_points(client):
    resp = client.get("/risk-profile/questionnaire")
    assert resp.status_code == 200
    body = resp.json()

    assert body["version"] == "v1"
    assert len(body["questions"]) == 4
    ids = {q["id"] for q in body["questions"]}
    assert ids == {"horizon", "drawdown_reaction", "experience", "goal"}

    horizon = next(q for q in body["questions"] if q["id"] == "horizon")
    assert horizon["weight"] == 3
    assert len(horizon["options"]) == 5
    assert horizon["options"][0] == {"value": "lt_1y", "label": "Within 1 year"}
    # deliberately no "points" field anywhere -- the frontend must never
    # be able to reconstruct/duplicate the scoring formula
    assert "points" not in horizon["options"][0]
