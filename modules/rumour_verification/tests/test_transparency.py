from datetime import date

import pytest

from src.corpus import load_corpus
from src.transparency import explain_all_candidates, format_full_trace
from src.verification import verify_rumour


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_explain_all_candidates_covers_every_considered_candidate(corpus):
    result = verify_rumour(
        "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative",
        corpus,
        rumour_date=date(2025, 2, 11),
    )
    explanations = explain_all_candidates(result)
    assert len(explanations) == len(result.all_candidates)
    assert len(explanations) > len(result.candidates)  # includes eliminated candidates too


def test_winner_is_flagged_and_has_no_failed_constraints(corpus):
    result = verify_rumour(
        "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative",
        corpus,
        rumour_date=date(2025, 2, 11),
    )
    explanations = explain_all_candidates(result)
    winners = [e for e in explanations if e.is_winner]
    assert len(winners) == 1
    assert winners[0].filing_id == "F001"
    assert winners[0].passed is True
    assert winners[0].failed_constraints == ()


def test_source_authority_distractor_is_eliminated_specifically_by_source_authority(corpus):
    # N003 is a near-duplicate news paraphrase of the real F001 filing --
    # same entity, same timing, but not an official filing. This is the
    # definition-of-done case from Module 5's own test suite: the
    # explanation must name source_authority specifically, not just "it lost."
    result = verify_rumour(
        "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative",
        corpus,
        rumour_date=date(2025, 2, 11),
    )
    explanations = {e.filing_id: e for e in explain_all_candidates(result)}
    n003 = explanations["N003"]
    assert n003.passed is False
    assert n003.failed_constraints == ("source_authority",)
    assert any("not an official exchange filing" in r for r in n003.reasons)


def test_entity_mismatched_candidates_are_eliminated_by_entity(corpus):
    result = verify_rumour(
        "IREDA has declared Gensol Engineering's loan accounts as fraud and reported it to the RBI",
        corpus,
        rumour_date=date(2026, 7, 13),
    )
    explanations = explain_all_candidates(result)
    unrelated = next(e for e in explanations if e.filing_id == "F001")  # Adani filing, unrelated to Gensol
    assert "entity" in unrelated.failed_constraints


def test_format_full_trace_names_the_winner_and_every_elimination_reason(corpus):
    result = verify_rumour(
        "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative",
        corpus,
        rumour_date=date(2025, 2, 11),
    )
    text = format_full_trace(result)
    assert "Winner: F001" in text
    assert "N003" in text
    assert "eliminated by: source_authority" in text
    assert "Candidates considered: 35" in text


def test_format_full_trace_handles_no_match_case(corpus):
    result = verify_rumour("Some completely unrelated company launched a new snack brand", corpus, rumour_date=date(2026, 1, 1))
    text = format_full_trace(result)
    assert "No candidate passed all three constraints" in text


def test_format_full_trace_never_claims_ai(corpus):
    result = verify_rumour(
        "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative",
        corpus,
        rumour_date=date(2025, 2, 11),
    )
    text = format_full_trace(result).lower()
    assert "ai-powered" not in text
    assert "artificial intelligence" not in text
