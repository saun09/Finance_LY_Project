import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models.suggestion_event import SuggestionEvent
from app.services import rumour_verification_bridge

USER = "api-rumour-user-1"
FAKE_URL = "https://fake-n8n.example.com/webhook/rumour-verification"

ADANI_RUMOUR = (
    "Adani Enterprises shares rally 4% on $686 million investment in "
    "not-for-profit healthcare initiative"
)

MATCHED_PAYLOAD = {
    "claim": ADANI_RUMOUR,
    "verdict": "denied",
    "confidence": 0.92,
    "company": "Adani",
    "ticker": "Adani",
    "official_evidence": [
        {
            "filing_id": "F001",
            "company_name": "Adani Enterprises",
            "filing_date": "2025-02-11",
            "filing_type": "clarification",
            "source_authority": "BSE",
            "source_url": "https://example.com/f001",
            "determination": "denied",
        }
    ],
    "news_evidence": [],
    "temporal_analysis": "",
    "reasoning": "Official BSE clarification denies the claim.",
    "caveats": [],
}

NO_MATCH_PAYLOAD = {
    "claim": "Some completely unrelated company launched a new snack brand",
    "verdict": None,
    "confidence": None,
    "company": "",
    "ticker": "",
    "official_evidence": [],
    "news_evidence": [],
    "temporal_analysis": "",
    "reasoning": "",
    "caveats": [],
}


def _fake_post(json_body: dict):
    def post(url, json=None, timeout=None):
        return httpx.Response(200, json=json_body, request=httpx.Request("POST", url))

    return post


@pytest.fixture()
def client(session, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", FAKE_URL)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_verify_rumour_via_api_logs_by_default(client, session, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(MATCHED_PAYLOAD))

    resp = client.post(
        f"/users/{USER}/rumour-verification",
        json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "denied"
    assert body["matched_score"] == 0.92
    assert body["matched_filing"]["filing_id"] == "F001"
    assert body["logged_event_id"] is not None

    event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").one()
    assert event.event_id == body["logged_event_id"]
    assert event.action_taken is None


def test_verify_rumour_with_log_event_false_does_not_log(client, session, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(MATCHED_PAYLOAD))

    resp = client.post(
        f"/users/{USER}/rumour-verification?log_event=false",
        json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["logged_event_id"] is None

    count = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").count()
    assert count == 0


def test_verify_rumour_no_match_via_api(client, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(NO_MATCH_PAYLOAD))

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


def test_repeated_verifications_each_log_their_own_event(client, session, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(MATCHED_PAYLOAD))

    client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"})
    client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"})

    count = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").count()
    assert count == 2


def test_n8n_timeout_surfaces_as_a_clean_502(client, monkeypatch):
    def post(url, json=None, timeout=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)

    resp = client.post(
        f"/users/{USER}/rumour-verification",
        json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 502
    assert "timed out" in resp.json()["detail"]


def test_missing_webhook_url_surfaces_as_a_clean_502(client, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", None)

    resp = client.post(
        f"/users/{USER}/rumour-verification",
        json={"rumour_text": ADANI_RUMOUR, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 502
    assert "not configured" in resp.json()["detail"]
