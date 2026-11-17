from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.models.rumour_verification_job import RumourVerificationJob
from app.models.suggestion_event import SuggestionEvent
from app.services import rumour_verification_bridge, rumour_verification_jobs

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


PUBLIC_URL = "https://api.example.com"


@pytest.fixture()
def n8n_calls(monkeypatch):
    """Stands in for n8n: accepts every run (like a Webhook node set to
    respond immediately) and records what it was sent, so a test can play
    the workflow's callback with the job id and token it received."""
    calls = []

    def post(url, json=None, timeout=None):
        calls.append(json)
        return httpx.Response(200, json={"message": "Workflow was started"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    return calls


@pytest.fixture()
def client(session, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", FAKE_URL)
    monkeypatch.setattr(rumour_verification_jobs, "PUBLIC_BASE_URL", PUBLIC_URL)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _start(client, rumour=ADANI_RUMOUR, query=""):
    resp = client.post(
        f"/users/{USER}/rumour-verification{query}",
        json={"rumour_text": rumour, "rumour_date": "2025-02-11"},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


def _callback(client, sent: dict, body, token=None):
    return client.post(
        f"/rumour-verification/jobs/{sent['job_id']}/result",
        json=body,
        headers={"X-Callback-Token": token if token is not None else sent["callback_token"]},
    )


def _poll(client, job_id):
    resp = client.get(f"/users/{USER}/rumour-verification/jobs/{job_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_start_returns_a_pending_job_and_hands_n8n_a_callback(client, n8n_calls):
    job = _start(client)

    assert job["status"] == "pending"
    assert job["result"] is None
    sent = n8n_calls[0]
    assert sent["job_id"] == job["job_id"]
    assert sent["callback_url"] == f"{PUBLIC_URL}/rumour-verification/jobs/{job['job_id']}/result"
    assert sent["callback_token"]
    assert _poll(client, job["job_id"])["status"] == "pending"


def test_callback_completes_the_job_and_logs_by_default(client, session, n8n_calls):
    job = _start(client)

    resp = _callback(client, n8n_calls[0], MATCHED_PAYLOAD)
    assert resp.status_code == 200

    polled = _poll(client, job["job_id"])
    assert polled["status"] == "completed"
    result = polled["result"]
    assert result["status"] == "denied"
    assert result["matched_score"] == 0.92
    assert result["matched_filing"]["filing_id"] == "F001"
    assert result["engine"] == "n8n_llm_workflow"
    assert result["logged_event_id"] is not None

    event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").one()
    assert event.event_id == result["logged_event_id"]
    assert event.action_taken is None


def test_log_event_false_does_not_log(client, session, n8n_calls):
    job = _start(client, query="?log_event=false")
    _callback(client, n8n_calls[0], MATCHED_PAYLOAD)

    assert _poll(client, job["job_id"])["result"]["logged_event_id"] is None
    assert session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").count() == 0


def test_no_match_result_is_still_logged(client, n8n_calls):
    job = _start(client, rumour="Some completely unrelated company launched a new snack brand")
    _callback(client, n8n_calls[0], NO_MATCH_PAYLOAD)

    result = _poll(client, job["job_id"])["result"]
    assert result["matched_filing"] is None
    assert result["status"] is None
    assert result["top_candidate_reasons"] == []
    assert result["logged_event_id"] is not None  # auditability doesn't depend on finding a match


def test_n8n_wrapping_the_result_in_a_one_item_list_is_accepted(client, n8n_calls):
    job = _start(client)
    _callback(client, n8n_calls[0], [MATCHED_PAYLOAD])
    assert _poll(client, job["job_id"])["result"]["status"] == "denied"


def test_callback_with_wrong_or_missing_token_is_rejected(client, n8n_calls):
    job = _start(client)

    assert _callback(client, n8n_calls[0], MATCHED_PAYLOAD, token="not-the-token").status_code == 403
    no_header = client.post(f"/rumour-verification/jobs/{job['job_id']}/result", json=MATCHED_PAYLOAD)
    assert no_header.status_code == 403
    assert _poll(client, job["job_id"])["status"] == "pending"


def test_callback_for_unknown_job_is_rejected_like_a_bad_token(client):
    resp = client.post("/rumour-verification/jobs/nope/result", json=MATCHED_PAYLOAD, headers={"X-Callback-Token": "x"})
    assert resp.status_code == 403


def test_a_repeated_callback_does_not_log_twice(client, session, n8n_calls):
    _start(client)
    _callback(client, n8n_calls[0], MATCHED_PAYLOAD)
    _callback(client, n8n_calls[0], MATCHED_PAYLOAD)
    assert session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").count() == 1


def test_error_callback_marks_the_job_failed(client, n8n_calls):
    job = _start(client)
    _callback(client, n8n_calls[0], {"error": "Verdict Synthesis Agent failed"})

    polled = _poll(client, job["job_id"])
    assert polled["status"] == "failed"
    assert "Verdict Synthesis Agent failed" in polled["error"]


def test_a_job_with_no_callback_expires_instead_of_polling_forever(client, session, n8n_calls):
    job = _start(client)
    row = session.get(RumourVerificationJob, job["job_id"])
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    session.commit()

    polled = _poll(client, job["job_id"])
    assert polled["status"] == "failed"
    assert "didn't report back" in polled["error"]


def test_another_users_job_is_not_visible(client, n8n_calls):
    job = _start(client)
    assert client.get(f"/users/someone-else/rumour-verification/jobs/{job['job_id']}").status_code == 404


def test_without_a_public_url_the_broader_workflow_says_why(client, monkeypatch):
    monkeypatch.setattr(rumour_verification_jobs, "PUBLIC_BASE_URL", "")
    resp = client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR})
    assert resp.status_code == 503
    assert "public URL" in resp.json()["detail"]


def test_n8n_refusing_the_run_fails_the_job_with_a_clean_502(client, monkeypatch):
    def post(url, json=None, timeout=None):
        return httpx.Response(524, text="<!DOCTYPE html><html>...</html>", request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    resp = client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR})
    assert resp.status_code == 502
    assert "HTTP 524" in resp.json()["detail"]
    assert "<html" not in resp.json()["detail"]


def test_missing_webhook_url_surfaces_as_a_clean_502(client, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", None)
    resp = client.post(f"/users/{USER}/rumour-verification", json={"rumour_text": ADANI_RUMOUR})
    assert resp.status_code == 502
    assert "not configured" in resp.json()["detail"]


# The real workflow's output: a verdict over company announcements and news,
# whose evidence items are articles (title + date), not exchange filings.
WORKFLOW_PAYLOAD = {
    "verdict": "SUPPORTED",
    "confidence": 0.95,
    "claim": "Nvidia CEO resigned.",
    "company": "Nvidia",
    "ticker": "NVDA",
    "claim_type": "Resignation",
    "summary": "The claim that Nvidia's CEO resigned is supported by official evidence.",
    "temporal_analysis": "The announcement was published before the rumour date.",
    "reasoning": "Nvidia's newsroom confirms the CEO's resignation.",
    "caveats": [],
    "official_evidence": [
        {"source": "Company Communications (search)", "title": "NVIDIA Announces CEO Transition", "publishedAt": "Thu, 12 Nov 2026 13:56:53 GMT"},
        {"source": "Company Communications (search)", "title": "A Message to Our Company", "publishedAt": "Sun, 08 Nov 2026 21:11:58 GMT"},
    ],
    "news_evidence": [
        {"source": "General (search)", "publishedAt": "Thu, 12 Nov 2026 22:37:44 GMT", "stance": "supports", "keyFact": "PBS reports that Jensen Huang resigned as Nvidia's CEO."},
        {"source": "General (search)"},  # nothing to show -- dropped
    ],
    "userId": "",
}


def test_workflow_verdict_is_returned_even_without_an_exchange_filing(client, n8n_calls):
    job = _start(client, rumour="Nvidia CEO resigned")
    _callback(client, n8n_calls[0], [WORKFLOW_PAYLOAD])

    result = _poll(client, job["job_id"])["result"]
    assert result["matched_filing"] is None  # still never fabricated
    workflow = result["workflow"]
    assert workflow["verdict"] == "SUPPORTED"
    assert workflow["confidence"] == 0.95
    assert workflow["summary"].startswith("The claim that Nvidia")
    assert workflow["official_sources_checked"] == 2
    assert workflow["news_evidence"] == [
        {
            "source": "General (search)",
            "title": None,
            "published_at": "Thu, 12 Nov 2026 22:37:44 GMT",
            "stance": "supports",
            "key_fact": "PBS reports that Jensen Huang resigned as Nvidia's CEO.",
        }
    ]
