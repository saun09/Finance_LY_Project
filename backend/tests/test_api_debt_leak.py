import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app

USER = "api-debtleak-user-1"


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
        f"/users/{USER}/expenses",
        json={"category": "Rent", "amount_paise": 20_000_00, "frequency": "monthly", "is_essential": True},
    )
    client.post(
        f"/users/{USER}/expenses",
        json={"category": "Streaming service", "amount_paise": 649_00, "frequency": "monthly", "is_essential": False},
    )
    emi_resp = client.post(
        f"/users/{USER}/emis",
        json={"lender": "Personal Loan Co", "amount_paise": 10_000_00, "remaining_tenure_months": 24, "annual_rate_bps": 1500},
    )
    return emi_resp.json()["id"]


def test_debt_leak_report_for_unknown_user_is_404(client):
    resp = client.get("/users/does-not-exist/debt-leak")
    assert resp.status_code == 404


def test_full_debt_leak_report_via_api(client):
    _onboard(client)
    resp = client.get(f"/users/{USER}/debt-leak")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_recoverable_annual_paise"] > 0
    assert body["expense_source_mode"] == "manual_only"
    assert body["avalanche_snowball"] is not None
    assert body["prepay_vs_invest"] is not None
    assert any(c["component_id"] == "idle_cash" for c in body["components"])
    assert "statement parser" in body["data_source_note"]


def test_credit_card_revolving_cost_endpoint(client):
    resp = client.post(
        f"/users/{USER}/debt-leak/credit-card-revolving-cost",
        json={"balance_paise": 50_000_00, "monthly_rate_bps": 350, "min_payment_pct_bps": 500, "min_payment_floor_paise": 50_00},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["effective_annual_rate_pct"] == "51.11"
    assert float(body["effective_annual_rate_pct"]) > float(body["nominal_annual_rate_pct"])


def test_refinance_breakeven_endpoint(client):
    emi_id = _onboard(client)
    resp = client.post(
        f"/users/{USER}/debt-leak/refinance-breakeven",
        json={"emi_id": emi_id, "new_annual_rate_bps": 900, "fees_paise": 5_000_00},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "breakeven_month" in body
    assert isinstance(body["beneficial"], bool)


def test_refinance_breakeven_unknown_emi_is_404(client):
    _onboard(client)
    resp = client.post(
        f"/users/{USER}/debt-leak/refinance-breakeven",
        json={"emi_id": "does-not-exist", "new_annual_rate_bps": 900, "fees_paise": 5_000_00},
    )
    assert resp.status_code == 404
