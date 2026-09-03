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


def test_get_endpoints_list_everything_recorded(client):
    client.put(
        f"/users/{USER}/profile",
        json={
            "income_paise": 80_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 1,
            "cash_balance_paise": 200_000_00,
        },
    )
    emi = client.post(
        f"/users/{USER}/emis",
        json={"lender": "HDFC Home Loan", "amount_paise": 25_000_00, "remaining_tenure_months": 240, "annual_rate_bps": 850},
    ).json()
    client.post(f"/users/{USER}/holdings", json={"description": "Mutual funds", "value_paise": 150_000_00})
    client.post(f"/users/{USER}/insurance-policies", json={"policy_type": "life", "sum_assured_paise": 5_000_000_00})
    expense = client.post(
        f"/users/{USER}/expenses",
        json={"category": "rent", "amount_paise": 20_000_00, "frequency": "monthly", "is_essential": True},
    ).json()

    profile_resp = client.get(f"/users/{USER}/profile")
    assert profile_resp.status_code == 200
    assert profile_resp.json()["user_id"] == USER

    emis_resp = client.get(f"/users/{USER}/emis")
    assert emis_resp.status_code == 200
    assert [e["id"] for e in emis_resp.json()] == [emi["id"]]
    assert emis_resp.json()[0]["closed_at"] is None

    holdings_resp = client.get(f"/users/{USER}/holdings")
    assert holdings_resp.status_code == 200
    assert len(holdings_resp.json()) == 1

    policies_resp = client.get(f"/users/{USER}/insurance-policies")
    assert policies_resp.status_code == 200
    assert len(policies_resp.json()) == 1

    expenses_resp = client.get(f"/users/{USER}/expenses")
    assert expenses_resp.status_code == 200
    assert [e["id"] for e in expenses_resp.json()] == [expense["id"]]

    # Closing/removing doesn't delete -- it should still show up, since a
    # management screen needs to see what was closed, not just what's active.
    client.post(f"/users/{USER}/emis/{emi['id']}/close")
    client.post(f"/users/{USER}/expenses/{expense['id']}/remove")

    emis_after_close = client.get(f"/users/{USER}/emis").json()
    assert len(emis_after_close) == 1
    assert emis_after_close[0]["id"] == emi["id"]
    assert emis_after_close[0]["closed_at"] is not None

    expenses_after_remove = client.get(f"/users/{USER}/expenses").json()
    assert len(expenses_after_remove) == 1
    assert expenses_after_remove[0]["id"] == expense["id"]
    assert expenses_after_remove[0]["removed_at"] is not None


def test_get_endpoints_for_unknown_user_return_404(client):
    assert client.get("/users/does-not-exist/profile").status_code == 404
    assert client.get("/users/does-not-exist/emis").status_code == 404
    assert client.get("/users/does-not-exist/insurance-policies").status_code == 404
    assert client.get("/users/does-not-exist/holdings").status_code == 404
    assert client.get("/users/does-not-exist/expenses").status_code == 404


def test_emi_for_unknown_user_returns_404(client):
    resp = client.post(
        f"/users/does-not-exist/emis",
        json={"lender": "X", "amount_paise": 1000, "remaining_tenure_months": 12, "annual_rate_bps": 1000},
    )
    assert resp.status_code == 404
