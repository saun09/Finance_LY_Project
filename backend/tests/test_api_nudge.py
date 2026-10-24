import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import get_session
from app.main import app
from app.models.suggestion_event import SuggestionEvent
from app.services.nudge_knowledge import KnowledgeChunk, retrieve

USER = "api-nudge-user-1"
OTHER = "api-nudge-user-2"


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
            "dependents_count": 2,
            "cash_balance_paise": 300_000_00,
        },
    )
    client.post(
        f"/users/{USER}/expenses",
        json={"category": "Rent", "amount_paise": 25_000_00, "frequency": "monthly", "is_essential": True},
    )
    client.post(
        f"/users/{USER}/emis",
        json={"lender": "QuickCash Finance", "amount_paise": 12_000_00, "remaining_tenure_months": 30, "annual_rate_bps": 1800, "purpose": "personal"},
    )
    client.post(
        f"/users/{USER}/emis",
        json={"lender": "City Bank", "amount_paise": 22_000_00, "remaining_tenure_months": 180, "annual_rate_bps": 850, "purpose": "home"},
    )


def test_briefing_for_user_without_onboarding_says_so(client):
    resp = client.get(f"/users/{USER}/nudge/briefing")
    assert resp.status_code == 200
    assert "not completed onboarding" in resp.json()["briefing"]


def test_briefing_covers_loans_debt_strategy_and_insurance_gap(client):
    _onboard(client)
    briefing = client.get(f"/users/{USER}/nudge/briefing", params={"surface": "allocation"}).json()["briefing"]

    assert "QuickCash Finance" in briefing and "18.00%" in briefing
    assert "City Bank" in briefing
    assert "avalanche" in briefing
    assert "no life or health insurance" in briefing
    assert "'allocation' screen" in briefing


def test_briefing_and_search_do_not_log_suggestion_events(client, session):
    _onboard(client)
    before = session.scalar(select(func.count()).select_from(SuggestionEvent))
    client.get(f"/users/{USER}/nudge/briefing")
    client.post(f"/users/{USER}/nudge/search", json={"query": "should I prepay my loan"})
    assert session.scalar(select(func.count()).select_from(SuggestionEvent)) == before


def test_search_finds_the_relevant_loan(client):
    _onboard(client)
    body = client.post(f"/users/{USER}/nudge/search", json={"query": "how much do I still owe on the home loan?"}).json()
    assert body["hits"][0]["topic"] == "loans"
    assert "City Bank" in body["result_text"]


def test_conversation_is_stored_and_recalled_later(client):
    _onboard(client)
    conv = client.post(f"/users/{USER}/nudge/conversations", json={"surface": "home"}).json()
    for role, text in [
        ("agent", "Hi, I'm Nudge."),
        ("user", "I'm saving for my sister's wedding in December next year."),
        ("agent", "Great, let's work out a monthly target for the wedding."),
    ]:
        assert client.post(f"/users/{USER}/nudge/conversations/{conv['id']}/messages", json={"role": role, "text": text}).status_code == 201
    ended = client.post(f"/users/{USER}/nudge/conversations/{conv['id']}/end", json={"elevenlabs_conversation_id": "conv_abc"}).json()
    assert ended["ended_at"] is not None
    assert ended["elevenlabs_conversation_id"] == "conv_abc"

    listing = client.get(f"/users/{USER}/nudge/conversations").json()
    assert listing[0]["message_count"] == 3
    assert "wedding" in listing[0]["preview"]

    detail = client.get(f"/users/{USER}/nudge/conversations/{conv['id']}").json()
    assert [m["role"] for m in detail["messages"]] == ["agent", "user", "agent"]

    # a later session's briefing remembers it, and search can retrieve it
    briefing = client.get(f"/users/{USER}/nudge/briefing").json()["briefing"]
    assert "RECENT CONVERSATIONS" in briefing and "wedding" in briefing
    hits = client.post(f"/users/{USER}/nudge/search", json={"query": "what did we discuss about the wedding"}).json()["hits"]
    assert hits[0]["topic"] == "conversation"


def test_search_excludes_the_conversation_in_progress(client):
    conv = client.post(f"/users/{USER}/nudge/conversations", json={"surface": "home"}).json()
    client.post(f"/users/{USER}/nudge/conversations/{conv['id']}/messages", json={"role": "user", "text": "Tell me about wedding savings"})
    hits = client.post(
        f"/users/{USER}/nudge/search", json={"query": "wedding", "conversation_id": conv["id"]}
    ).json()["hits"]
    assert all(h["topic"] != "conversation" for h in hits)


def test_conversations_are_scoped_to_their_user(client):
    conv = client.post(f"/users/{USER}/nudge/conversations", json={"surface": "home"}).json()
    assert client.get(f"/users/{OTHER}/nudge/conversations/{conv['id']}").status_code == 404
    resp = client.post(f"/users/{OTHER}/nudge/conversations/{conv['id']}/messages", json={"role": "user", "text": "hi"})
    assert resp.status_code == 404
    assert client.get(f"/users/{OTHER}/nudge/conversations").json() == []


def test_blank_message_is_rejected(client):
    conv = client.post(f"/users/{USER}/nudge/conversations", json={"surface": "home"}).json()
    resp = client.post(f"/users/{USER}/nudge/conversations/{conv['id']}/messages", json={"role": "user", "text": "   "})
    assert resp.status_code == 422


def test_retrieve_falls_back_to_overview_when_nothing_matches():
    chunks = [KnowledgeChunk("loans", "loans", "Loan from A."), KnowledgeChunk("overview", "overview", "Income Rs 1.")]
    hits = retrieve(chunks, "zzzz qqqq")
    assert [h.chunk.chunk_id for h in hits] == ["overview"]
