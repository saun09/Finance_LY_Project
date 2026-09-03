import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-onboard-user-1"


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_full_onboarding_flow_via_api(client):
    profile_resp = client.put(
        f"/users/{USER}/profile",
        json={
            "income_paise": 80_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 1,
            "cash_balance_paise": 200_000_00,
        },
    )
    assert profile_resp.status_code == 200
    assert profile_resp.json()["user_id"] == USER

    emi_resp = client.post(
        f"/users/{USER}/emis",
        json={"lender": "HDFC Home Loan", "amount_paise": 25_000_00, "remaining_tenure_months": 240, "annual_rate_bps": 850},
    )
    assert emi_resp.status_code == 200

    holding_resp = client.post(f"/users/{USER}/holdings", json={"description": "Mutual funds", "value_paise": 150_000_00})
    assert holding_resp.status_code == 200

    expense_resp = client.post(
        f"/users/{USER}/expenses",
        json={"category": "rent", "amount_paise": 20_000_00, "frequency": "monthly", "is_essential": True},
    )
    assert expense_resp.status_code == 200

    decision_resp = client.get(f"/users/{USER}/expense-source-decision")
    assert decision_resp.status_code == 200
    assert decision_resp.json()["mode"] == "manual_only"
    assert decision_resp.json()["is_explicit_decision"] is False

    position_resp = client.get(f"/users/{USER}/financial-position")
    assert position_resp.status_code == 200
    body = position_resp.json()
    assert body["total_monthly_emi_paise"] == 25_000_00
    assert body["net_worth_paise"] < 0  # home loan PV dwarfs cash + one holding here

    complete_resp = client.post(f"/users/{USER}/complete-onboarding")
    assert complete_resp.status_code == 200
    snapshot = complete_resp.json()
    assert snapshot["user_id"] == USER
    assert snapshot["income"] == 80_000_00


def test_emi_for_unknown_user_returns_404(client):
    resp = client.post(
        f"/users/does-not-exist/emis",
        json={"lender": "X", "amount_paise": 1000, "remaining_tenure_months": 12, "annual_rate_bps": 1000},
    )
    assert resp.status_code == 404
