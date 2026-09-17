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
    assert body["reasoning"]["rule_lookup"]["which_rule"] == "v3-hybrid"
    raw = resp.text
    assert "Equity fund" not in raw  # Module 4's hard constraint holds through the transparency view too


def test_index_reflects_computed_decisions(client):
    _onboard(client)
    counts = client.get(f"/users/{USER}/transparency").json()["counts_by_module_source"]
    assert counts.get("risk_profile", 0) >= 1
    assert counts.get("allocation", 0) >= 1


# --- sections and value hints reach the client ---


def test_trace_response_carries_per_section_availability(client):
    _onboard(client)
    body = client.get(f"/users/{USER}/transparency/risk_profile").json()
    sections = body["sections"]
    assert [s["key"] for s in sections] == ["questionnaire", "capacity_layer", "outcome"]
    assert all(s["available"] for s in sections)
    assert all(s["title"] for s in sections)


def test_trace_response_declares_units_so_the_client_never_guesses(client):
    _onboard(client)
    body = client.get(f"/users/{USER}/transparency/risk_profile").json()
    assert body["value_hint_rules_version"]
    assert body["value_hints"].get("monthly_income_paise") == "paise"
    assert body["value_hints"].get("final_tier") == "tier"


# --- history and comparison ---


def test_decision_history_endpoint_lists_every_decision(client):
    _onboard(client)
    client.post(f"/users/{USER}/risk-profile", json={"answers": {**AGGRESSIVE_ANSWERS, "horizon": "lt_1y"}})

    resp = client.get(f"/users/{USER}/transparency/risk_profile/history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert all(row["event_id"] for row in body)
    assert all(row["headline"] for row in body)


def test_history_for_unknown_type_is_404(client):
    assert client.get(f"/users/{USER}/transparency/nope/history").status_code == 404


def test_compare_endpoint_names_the_input_that_moved(client):
    _onboard(client)
    client.post(f"/users/{USER}/risk-profile", json={"answers": {**AGGRESSIVE_ANSWERS, "horizon": "lt_1y"}})
    history = client.get(f"/users/{USER}/transparency/risk_profile/history").json()
    newer, older = history[0]["event_id"], history[1]["event_id"]

    resp = client.get(
        f"/users/{USER}/transparency/risk_profile/compare",
        params={"before_event_id": older, "after_event_id": newer},
    )
    assert resp.status_code == 200
    body = resp.json()
    paths = {c["path"] for c in body["changes"]}
    assert "questionnaire.answers.horizon" in paths
    assert body["before_headline"] and body["after_headline"]


def test_compare_with_an_unknown_event_id_is_404(client):
    _onboard(client)
    history = client.get(f"/users/{USER}/transparency/risk_profile/history").json()
    resp = client.get(
        f"/users/{USER}/transparency/risk_profile/compare",
        params={"before_event_id": history[0]["event_id"], "after_event_id": "does-not-exist"},
    )
    assert resp.status_code == 404


# --- contest ---


def test_contest_reason_codes_are_served_not_hardcoded_client_side(client):
    resp = client.get(f"/users/{USER}/transparency/contest-reasons")
    assert resp.status_code == 200
    assert "input_wrong" in resp.json()


def test_contesting_a_trace_marks_the_decision_and_returns_the_updated_trace(client):
    _onboard(client)
    trace = client.get(f"/users/{USER}/transparency/risk_profile").json()
    assert trace["contested"] is False

    resp = client.post(
        f"/users/{USER}/transparency/risk_profile/contest",
        json={"event_id": trace["event_id"], "reason_code": "input_wrong", "note": "buffer is wrong"},
    )
    assert resp.status_code == 200
    assert resp.json()["contested"] is True
    assert resp.json()["contest_reason_code"] == "input_wrong"

    # and it is visible on the next read, because it was written to the event log
    assert client.get(f"/users/{USER}/transparency/risk_profile").json()["contested"] is True


def test_contest_with_an_unrecognized_reason_is_422(client):
    _onboard(client)
    trace = client.get(f"/users/{USER}/transparency/risk_profile").json()
    resp = client.post(
        f"/users/{USER}/transparency/risk_profile/contest",
        json={"event_id": trace["event_id"], "reason_code": "made_up"},
    )
    assert resp.status_code == 422
