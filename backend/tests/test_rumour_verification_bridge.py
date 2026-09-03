from datetime import date

from app.models.suggestion_event import SuggestionEvent
from app.services.rumour_verification_bridge import (
    log_verification_event,
    run_verification,
    verification_result_to_suggested_value,
)

USER = "bridge-user-1"

ADANI_RUMOUR = (
    "Adani Enterprises shares rally 4% on $686 million investment in "
    "not-for-profit healthcare initiative"
)


def test_run_verification_calls_module_5_unchanged_and_finds_the_real_match():
    result = run_verification(ADANI_RUMOUR, rumour_date=date(2025, 2, 11))
    assert result.matched_filing is not None
    assert result.matched_filing.filing_id == "F001"
    assert result.status == "denied"


def test_run_verification_with_no_match_returns_none_gracefully():
    result = run_verification("Some completely unrelated company launched a new snack brand", rumour_date=date(2026, 1, 1))
    assert result.matched_filing is None
    assert result.status is None


def test_corpus_is_cached_across_calls():
    from app.services.rumour_verification_bridge import _cached_corpus

    first = _cached_corpus()
    second = _cached_corpus()
    assert first is second  # same tuple object, not reloaded from disk


def test_suggested_value_shape_is_json_safe_and_never_recomputes():
    result = run_verification(ADANI_RUMOUR, rumour_date=date(2025, 2, 11))
    value = verification_result_to_suggested_value(result)

    assert value["matched_filing"]["filing_id"] == "F001"
    assert value["status"] == "denied"
    assert isinstance(value["rumour_date"], str)  # date serialized, not a date object
    assert value["candidates_considered"] == len(result.all_candidates)
    assert value["candidates_passing"] == len(result.candidates)
    assert value["top_candidate_reasons"] == list(result.candidates[0].checks.reasons())


def test_suggested_value_for_no_match_has_null_filing():
    result = run_verification("Some completely unrelated company launched a new snack brand", rumour_date=date(2026, 1, 1))
    value = verification_result_to_suggested_value(result)
    assert value["matched_filing"] is None
    assert value["top_candidate_reasons"] == []


def test_log_verification_event_writes_a_suggestion_event_for_auditability_only(session):
    result = run_verification(ADANI_RUMOUR, rumour_date=date(2025, 2, 11))
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
