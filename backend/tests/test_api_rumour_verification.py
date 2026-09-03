import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models.suggestion_event import SuggestionEvent

USER = "api-rumour-user-1"

ADANI_RUMOUR = (
    "Adani Enterprises shares rally 4% on $686 million investment in "
    "not-for-profit healthcare initiative"
)


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_verify_rumour_via_api_logs_by_default(client, session):
    resp = client.post(
        f"/users/{USER}/rumour-verification",
        json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "denied"
    assert body["matched_filing"]["filing_id"] == "F001"
    assert body["logged_event_id"] is not None

    event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").one()
    assert event.event_id == body["logged_event_id"]
    assert event.action_taken is None


def test_verify_rumour_with_log_event_false_does_not_log(client, session):
    resp = client.post(
        f"/users/{USER}/rumour-verification?log_event=false",
        json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["logged_event_id"] is None

    count = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").count()
    assert count == 0


def test_verify_rumour_no_match_via_api(client):
    resp = client.post(
        f"/users/{USER}/rumour-verification",
        json={"rumour_text": "Some completely unrelated company launched a new snack brand", "rumour_date": "2026-01-01"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched_filing"] is None
    assert body["status"] is None
    assert body["top_candidate_reasons"] == []
    assert body["logged_event_id"] is not None  # still logged, auditability doesn't depend on finding a match


def test_repeated_verifications_each_log_their_own_event(client, session):
    client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"})
    client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"})

    count = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").count()
    assert count == 2
