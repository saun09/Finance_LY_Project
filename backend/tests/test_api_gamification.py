import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-gamify-user-1"


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _onboard(client, cash_paise=600_000_00):
    client.put(
        f"/users/{USER}/profile",
        json={
            "income_paise": 100_000_00,
            "income_stability": "regular",
            "employment_type": "salaried",
            "dependents_count": 0,
            "cash_balance_paise": cash_paise,
        },
    )
    client.post(
        f"/users/{USER}/expenses",
        json={"category": "Rent", "amount_paise": 100_000_00, "frequency": "monthly", "is_essential": True},
    )


def test_check_milestones_for_unknown_user_is_404(client):
    resp = client.post("/users/does-not-exist/gamification/check")
    assert resp.status_code == 404


def test_buffer_milestones_via_api(client):
    _onboard(client)  # 6,00,000 cash / 1,00,000 essential = 6 months
    resp = client.post(f"/users/{USER}/gamification/check")
    assert resp.status_code == 200
    ids = {m["milestone_id"] for m in resp.json()}
    assert ids == {"buffer_months_1", "buffer_months_2", "buffer_months_4", "buffer_months_6"}

    # not re-awarded on a second check
    resp2 = client.post(f"/users/{USER}/gamification/check")
    assert resp2.json() == []


def test_debt_free_milestone_via_close_emi_endpoint(client):
    _onboard(client, cash_paise=50_000_00)
    emi_resp = client.post(
        f"/users/{USER}/emis",
        json={"lender": "Loan Co", "amount_paise": 5_000_00, "remaining_tenure_months": 12, "annual_rate_bps": 1000},
    )
    emi_id = emi_resp.json()["id"]

    before = client.post(f"/users/{USER}/gamification/check").json()
    assert "debt_free" not in {m["milestone_id"] for m in before}

    close_resp = client.post(f"/users/{USER}/emis/{emi_id}/close")
    assert close_resp.status_code == 200

    after = client.post(f"/users/{USER}/gamification/check").json()
    assert "debt_free" in {m["milestone_id"] for m in after}


def test_subscription_cancelled_via_remove_expense_endpoint(client):
    _onboard(client)
    sub_resp = client.post(
        f"/users/{USER}/expenses",
        json={"category": "Streaming service", "amount_paise": 649_00, "frequency": "monthly", "is_essential": False},
    )
    item_id = sub_resp.json()["id"]

    remove_resp = client.post(f"/users/{USER}/expenses/{item_id}/remove")
    assert remove_resp.status_code == 200

    result = client.post(f"/users/{USER}/gamification/check").json()
    assert "subscriptions_cancelled_1" in {m["milestone_id"] for m in result}


def test_close_unknown_emi_is_404(client):
    _onboard(client)
    resp = client.post(f"/users/{USER}/emis/does-not-exist/close")
    assert resp.status_code == 404


def test_milestone_history_reflects_prior_checks(client):
    _onboard(client)
    client.post(f"/users/{USER}/gamification/check")

    history = client.get(f"/users/{USER}/gamification/history").json()
    assert len(history["milestones"]) == 4
