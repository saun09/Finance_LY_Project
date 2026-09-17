"""Module 5's explainable engine, as reached from the app.

The point of these tests is the distinction the project's explainability
claim rests on: this engine can name which constraint eliminated which
candidate filing and why the winner ranked first, and the n8n workflow
cannot. If the elimination trace ever stops reaching the app, the claim
quietly becomes false again -- which is exactly what happened when
`format_full_trace` was reachable only from demo.py.
"""

from datetime import date

import pytest

from app.services.event_log import get_user_event_history
from app.services.rumour_local_engine import (
    ENGINE_NAME,
    MODULE_SOURCE,
    local_engine_available,
    log_local_verification_event,
    run_local_verification,
    verification_result_to_suggested_value,
)
from app.services.transparency import (
    DECISION_TYPES,
    RETRIEVAL_EXPLANATION_LABEL,
    _missing_fields,
    build_trace,
    get_trace,
)

pytestmark = pytest.mark.skipif(
    not local_engine_available(),
    reason="Module 5's research dependencies (scikit-learn/numpy) are not installed",
)

USER = "local-engine-user-1"

ADANI_RUMOUR = (
    "Adani Enterprises shares rally 4% on $686 million investment in "
    "not-for-profit healthcare initiative"
)
ADANI_DATE = date(2025, 2, 11)


@pytest.fixture(scope="module")
def result():
    return run_local_verification(ADANI_RUMOUR, rumour_date=ADANI_DATE)


def test_the_engine_returns_every_candidate_it_considered_not_only_the_winner(result):
    payload = verification_result_to_suggested_value(result)
    assert payload["candidates_considered"] == len(result.all_candidates)
    assert payload["candidates_considered"] > payload["candidates_passing"]
    assert payload["candidates_eliminated"] > 0


def test_each_eliminated_candidate_names_the_constraint_that_killed_it(result):
    payload = verification_result_to_suggested_value(result)
    eliminated = [c for c in payload["candidate_explanations"] if not c["eligible"]]
    assert eliminated
    for candidate in eliminated:
        assert candidate["failed_constraints"], f"{candidate['filing_id']} failed but names no reason"
        assert set(candidate["failed_constraints"]) <= {
            "entity", "temporal", "source_authority", "score_floor",
        }
        assert candidate["reasons"]


def test_a_candidate_stopped_only_by_the_similarity_floor_still_names_a_reason(result):
    """The floor is a real elimination reason. If the trace omitted it, a
    candidate could pass every check the explanation mentions and still not
    be returned -- an explanation that cannot account for the verdict."""
    payload = verification_result_to_suggested_value(result)
    floor_only = [
        c for c in payload["candidate_explanations"]
        if c["passed"] and not c["met_score_floor"]
    ]
    for candidate in floor_only:
        assert candidate["failed_constraints"] == ["score_floor"]
        assert candidate["eligible"] is False
    assert payload["min_score"] > 0


def test_the_winner_passed_every_constraint_and_the_trace_says_why_it_ranked_first(result):
    payload = verification_result_to_suggested_value(result)
    winners = [c for c in payload["candidate_explanations"] if c["is_winner"]]
    assert len(winners) == 1
    assert winners[0]["passed"] is True
    assert winners[0]["failed_constraints"] == []
    assert winners[0]["filing_id"] in payload["why_ranked_first"]
    # a comparative claim, not just an assertion that it won
    why = payload["why_ranked_first"]
    assert "highest" in why or "only eligible candidate" in why


def test_eliminated_counts_are_broken_down_by_constraint(result):
    payload = verification_result_to_suggested_value(result)
    assert payload["eliminated_by_constraint"]
    assert sum(payload["eliminated_by_constraint"].values()) >= payload["candidates_eliminated"]


def test_full_trace_text_is_human_readable_and_lists_eliminations(result):
    payload = verification_result_to_suggested_value(result)
    text = payload["full_trace_text"]
    assert "Eliminated" in text
    assert "eliminated by:" in text


def test_payload_is_json_safe(result):
    import json

    json.dumps(verification_result_to_suggested_value(result))  # must not raise


# --- the logged event, and Module 9's replay of it ---


def test_logged_event_carries_the_whole_elimination_trace(session, result):
    log_local_verification_event(session, USER, result)
    events = get_user_event_history(session, USER, module_source=MODULE_SOURCE, limit=1)
    assert events

    stored = events[0].suggested_value
    assert stored["candidate_explanations"], "the trace must be stored, not recomputed on read"
    assert events[0].market_context["engine"] == ENGINE_NAME
    assert events[0].market_context["constraints_applied"] == ["entity", "temporal", "source_authority", "score_floor"]


def test_logged_event_satisfies_its_transparency_spec(session, result):
    """The contract test for this decision type -- see
    test_transparency_contract.py for why these exist at all."""
    log_local_verification_event(session, USER, result)
    event = get_user_event_history(session, USER, module_source=MODULE_SOURCE, limit=1)[0]
    spec = DECISION_TYPES[MODULE_SOURCE]

    assert _missing_fields(event, spec) == ()
    trace = build_trace(event, spec)
    assert trace.gap_detected is False


def test_module_9_replays_the_elimination_trace_from_the_log(session, result):
    log_local_verification_event(session, USER, result)
    trace = get_trace(session, USER, MODULE_SOURCE)

    assert trace.framing_label == RETRIEVAL_EXPLANATION_LABEL
    eliminations = trace.reasoning["eliminations"]
    assert eliminations["per_candidate"]
    assert eliminations["constraints_applied"] == ["entity", "temporal", "source_authority", "score_floor"]
    assert trace.reasoning["why_this_filing_won"]["why_ranked_first"]


def test_this_is_the_only_decision_type_allowed_to_claim_an_explanation():
    """Guards the distinction directly: if a second spec ever adopts the
    retrieval-explanation label, someone has to justify it here."""
    explaining = [
        source for source, spec in DECISION_TYPES.items()
        if spec.framing_label == RETRIEVAL_EXPLANATION_LABEL
    ]
    assert explaining == [MODULE_SOURCE]


def test_the_explanation_label_still_never_claims_ai():
    """TF-IDF cosine similarity plus three rule-based filters is a retrieval
    pipeline, not a model. 'Explanation' is earned here; 'AI' is not."""
    label = RETRIEVAL_EXPLANATION_LABEL.lower()
    assert "ai" not in label.split()
    assert "model" not in label
    assert "neural" not in label
