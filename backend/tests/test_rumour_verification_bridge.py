from datetime import date

import httpx
import pytest

from app.models.suggestion_event import SuggestionEvent
from app.services import rumour_verification_bridge
from app.services.rumour_verification_bridge import (
    log_verification_event,
    parse_n8n_result,
    start_verification,
    verification_result_to_suggested_value,
)

USER = "bridge-user-1"
FAKE_URL = "https://fake-n8n.example.com/webhook/rumour-verification"

MATCHED_PAYLOAD = {
    "claim": "Adani Group is going to acquire a stake in Paytm.",
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
    "temporal_analysis": "Filed within the same news cycle as the rumour.",
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


def _fake_post(json_body=None, status_code: int = 200):
    def post(url, json=None, timeout=None):
        return httpx.Response(status_code, json=json_body, request=httpx.Request("POST", url))

    return post


@pytest.fixture(autouse=True)
def _configured_webhook_url(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", FAKE_URL)


def _start(**overrides):
    kwargs = dict(
        job_id="job-1",
        callback_url="https://api.example.com/rumour-verification/jobs/job-1/result",
        callback_token="tok",
    )
    kwargs.update(overrides)
    start_verification("Adani Group is going to acquire a stake in Paytm.", **kwargs)


# --- start_verification: hand-off to n8n ------------------------------------


def test_start_sends_the_workflow_fields_plus_callback_details(monkeypatch):
    captured = {}

    def post(url, json=None, timeout=None):
        captured.update(url=url, json=json, timeout=timeout)
        return httpx.Response(200, text="Workflow was started", request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    _start(rumour_date=date(2025, 2, 11), company_name="Adani")

    assert captured["url"] == FAKE_URL
    assert captured["json"] == {
        "rumour": "Adani Group is going to acquire a stake in Paytm.",
        "company": "Adani",
        "ticker": "Adani",
        "rumour_date": "2025-02-11",
        "evaluated_at": "",
        "job_id": "job-1",
        "callback_url": "https://api.example.com/rumour-verification/jobs/job-1/result",
        "callback_token": "tok",
    }
    # only the hand-off is awaited -- well under n8n Cloud's ~100s cut-off
    assert captured["timeout"] < 100


def test_start_ignores_whatever_n8n_acknowledges_with(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post({"message": "Workflow was started"}))
    _start()  # no exception, nothing parsed


def test_start_raises_when_webhook_url_missing(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", None)
    with pytest.raises(RuntimeError, match="not configured"):
        _start()


def test_start_wraps_timeout_cleanly(monkeypatch):
    def post(url, json=None, timeout=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(rumour_verification_bridge.N8NTimeoutError):
        _start()


def test_start_wraps_connection_errors_cleanly(monkeypatch):
    def post(url, json=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(RuntimeError, match="Could not connect"):
        _start()


def test_start_reports_non_2xx_without_dumping_the_html_page(monkeypatch):
    def post(url, json=None, timeout=None):
        return httpx.Response(524, text="<!DOCTYPE html><html>...</html>", request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(RuntimeError, match="HTTP 524") as exc_info:
        _start()
    assert "<html" not in str(exc_info.value)


# --- parse_n8n_result: the callback body ------------------------------------


def test_parse_maps_a_real_match():
    result = parse_n8n_result(MATCHED_PAYLOAD, rumour_text="x", rumour_date=date(2025, 2, 11), company_name="Adani")
    assert result.verdict == "denied"
    assert result.confidence == 0.92
    assert result.official_evidence[0]["filing_id"] == "F001"
    assert result.rumour_date == date(2025, 2, 11)


def test_parse_no_match_returns_empty_gracefully():
    result = parse_n8n_result(NO_MATCH_PAYLOAD, rumour_text="x")
    assert result.official_evidence == []
    assert result.verdict is None


def test_parse_rejects_non_object_json_cleanly():
    with pytest.raises(RuntimeError, match="malformed response"):
        parse_n8n_result(["not", "an", "object"], rumour_text="x")


def test_malformed_confidence_type_is_dropped_not_crashed():
    result = parse_n8n_result(dict(MATCHED_PAYLOAD, confidence="high"), rumour_text="x")
    assert result.confidence is None


def test_parse_falls_back_to_the_submitted_text_when_claim_is_missing():
    payload = {k: v for k, v in MATCHED_PAYLOAD.items() if k != "claim"}
    assert parse_n8n_result(payload, rumour_text="what the user typed").query_text == "what the user typed"


def test_suggested_value_shape_is_json_safe():
    result = parse_n8n_result(MATCHED_PAYLOAD, rumour_text="Adani Group is going to acquire a stake in Paytm.", rumour_date=date(2025, 2, 11))
    value = verification_result_to_suggested_value(result)

    assert value["matched_filing"]["filing_id"] == "F001"
    assert value["status"] == "denied"
    assert value["matched_score"] == 0.92
    assert isinstance(value["rumour_date"], str)  # date serialized, not a date object
    assert isinstance(value["matched_filing"]["filing_date"], str)  # never a raw date object
    assert value["candidates_considered"] == 1
    assert value["candidates_passing"] == 1


def test_suggested_value_for_no_match_has_null_filing():
    result = parse_n8n_result(NO_MATCH_PAYLOAD, rumour_text="Some completely unrelated company launched a new snack brand", rumour_date=date(2026, 1, 1))
    value = verification_result_to_suggested_value(result)
    assert value["matched_filing"] is None
    assert value["top_candidate_reasons"] == []


def test_incomplete_evidence_never_fabricates_a_matched_filing():
    # official_evidence is non-empty, but missing filing_id/date/authority --
    # this must still resolve to a null matched_filing, not a half-invented one.
    incomplete_payload = dict(MATCHED_PAYLOAD, official_evidence=[{"company_name": "Adani Enterprises"}])
    result = parse_n8n_result(incomplete_payload, rumour_text="anything")
    value = verification_result_to_suggested_value(result)
    assert value["matched_filing"] is None


def test_log_verification_event_writes_a_suggestion_event_for_auditability_only(session):
    result = parse_n8n_result(MATCHED_PAYLOAD, rumour_text="Adani Group is going to acquire a stake in Paytm.", rumour_date=date(2025, 2, 11))
    event = log_verification_event(session, USER, result)

    assert event.module_source == "rumour_verification"
    assert event.user_id == USER
    assert event.suggested_value["matched_filing"]["filing_id"] == "F001"
    # never touches the accept/edit/reject lifecycle
    assert event.action_taken is None
    assert event.chosen_value is None
    assert event.funded is None

    stored = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="rumour_verification").one()
    assert stored.event_id == event.event_id
