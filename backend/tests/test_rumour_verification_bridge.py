from datetime import date

import httpx
import pytest

from app.models.suggestion_event import SuggestionEvent
from app.services import rumour_verification_bridge
from app.services.rumour_verification_bridge import (
    log_verification_event,
    run_verification,
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


def _fake_post(json_body: dict, status_code: int = 200):
    def post(url, json=None, timeout=None):
        return httpx.Response(status_code, json=json_body, request=httpx.Request("POST", url))

    return post


@pytest.fixture(autouse=True)
def _configured_webhook_url(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", FAKE_URL)


def test_run_verification_calls_n8n_and_maps_a_real_match(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(MATCHED_PAYLOAD))

    result = run_verification("Adani Group is going to acquire a stake in Paytm.", rumour_date=date(2025, 2, 11), company_name="Adani")

    assert result.verdict == "denied"
    assert result.confidence == 0.92
    assert result.official_evidence[0]["filing_id"] == "F001"


def test_run_verification_sends_the_translated_payload(monkeypatch):
    captured = {}

    def post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return httpx.Response(200, json=MATCHED_PAYLOAD, request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)

    run_verification("Adani Group is going to acquire a stake in Paytm.", rumour_date=date(2025, 2, 11), company_name="Adani")

    assert captured["url"] == FAKE_URL
    assert captured["json"] == {
        "rumour": "Adani Group is going to acquire a stake in Paytm.",
        "company": "Adani",
        "ticker": "Adani",
        "rumour_date": "2025-02-11",
        "evaluated_at": "",
    }


def test_run_verification_with_no_match_returns_none_gracefully(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(NO_MATCH_PAYLOAD))

    result = run_verification("Some completely unrelated company launched a new snack brand", rumour_date=date(2026, 1, 1))
    assert result.official_evidence == []
    assert result.verdict is None


def test_run_verification_raises_when_webhook_url_missing(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge, "N8N_WEBHOOK_URL", None)
    with pytest.raises(RuntimeError, match="not configured"):
        run_verification("anything")


def test_run_verification_wraps_timeout_cleanly(monkeypatch):
    def post(url, json=None, timeout=None):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(RuntimeError, match="timed out"):
        run_verification("anything")


def test_run_verification_wraps_connection_errors_cleanly(monkeypatch):
    def post(url, json=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(RuntimeError, match="Could not connect"):
        run_verification("anything")


def test_run_verification_wraps_non_2xx_response_cleanly(monkeypatch):
    def post(url, json=None, timeout=None):
        return httpx.Response(500, text="internal error", request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        run_verification("anything")


def test_run_verification_wraps_invalid_json_cleanly(monkeypatch):
    def post(url, json=None, timeout=None):
        return httpx.Response(200, content=b"not json", request=httpx.Request("POST", url))

    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", post)
    with pytest.raises(RuntimeError, match="invalid JSON"):
        run_verification("anything")


def test_run_verification_rejects_non_object_json_cleanly(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(["not", "an", "object"]))
    with pytest.raises(RuntimeError, match="malformed response"):
        run_verification("anything")


def test_malformed_confidence_type_is_dropped_not_crashed(monkeypatch):
    bad_payload = dict(MATCHED_PAYLOAD, confidence="high")
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(bad_payload))

    result = run_verification("anything")
    assert result.confidence is None


def test_suggested_value_shape_is_json_safe(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(MATCHED_PAYLOAD))

    result = run_verification("Adani Group is going to acquire a stake in Paytm.", rumour_date=date(2025, 2, 11))
    value = verification_result_to_suggested_value(result)

    assert value["matched_filing"]["filing_id"] == "F001"
    assert value["status"] == "denied"
    assert value["matched_score"] == 0.92
    assert isinstance(value["rumour_date"], str)  # date serialized, not a date object
    assert isinstance(value["matched_filing"]["filing_date"], str)  # never a raw date object
    assert value["candidates_considered"] == 1
    assert value["candidates_passing"] == 1


def test_suggested_value_for_no_match_has_null_filing(monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(NO_MATCH_PAYLOAD))

    result = run_verification("Some completely unrelated company launched a new snack brand", rumour_date=date(2026, 1, 1))
    value = verification_result_to_suggested_value(result)
    assert value["matched_filing"] is None
    assert value["top_candidate_reasons"] == []


def test_incomplete_evidence_never_fabricates_a_matched_filing(monkeypatch):
    # official_evidence is non-empty, but missing filing_id/date/authority --
    # this must still resolve to a null matched_filing, not a half-invented one.
    incomplete_payload = dict(MATCHED_PAYLOAD, official_evidence=[{"company_name": "Adani Enterprises"}])
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(incomplete_payload))

    result = run_verification("anything")
    value = verification_result_to_suggested_value(result)
    assert value["matched_filing"] is None


def test_log_verification_event_writes_a_suggestion_event_for_auditability_only(session, monkeypatch):
    monkeypatch.setattr(rumour_verification_bridge.httpx, "post", _fake_post(MATCHED_PAYLOAD))

    result = run_verification("Adani Group is going to acquire a stake in Paytm.", rumour_date=date(2025, 2, 11))
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
