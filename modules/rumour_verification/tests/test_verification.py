from datetime import date, datetime

import pytest

from src.corpus import load_corpus
from src.verification import verify_rumour


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_verify_rumour_matches_and_labels_confirmed_case(corpus):
    result = verify_rumour(
        "IREDA has declared Gensol Engineering's loan accounts as fraud and reported it to the RBI",
        corpus,
        rumour_date=date(2026, 7, 13),
        evaluated_at=datetime(2026, 7, 15),
    )
    assert result.matched_filing is not None
    assert result.matched_filing.filing_id == "F003"
    assert result.status == "confirmed"


def test_verify_rumour_matches_and_labels_denied_case():
    corpus = load_corpus()
    result = verify_rumour(
        "There is no discussion of Hinduja Group bringing in a strategic partner for IndusInd Bank",
        corpus,
        rumour_date=date(2025, 12, 3),
        evaluated_at=datetime(2025, 12, 6),
    )
    assert result.matched_filing is not None
    assert result.matched_filing.filing_id == "F011"
    assert result.status == "denied"


def test_verify_rumour_labels_non_committal_case_as_unaddressed_once_overdue():
    corpus = load_corpus()
    result = verify_rumour(
        "Government finalises revised Fairfax Financial bid for IDBI Bank stake",
        corpus,
        rumour_date=date(2025, 1, 25),
        evaluated_at=datetime(2025, 1, 28),  # well past the 24h window
    )
    assert result.matched_filing is not None
    assert result.matched_filing.filing_id == "F004"
    assert result.status == "unaddressed"


def test_verify_rumour_without_rumour_date_still_matches_but_has_no_status():
    corpus = load_corpus()
    result = verify_rumour(
        "IREDA has declared Gensol Engineering's loan accounts as fraud and reported it to the RBI",
        corpus,
    )
    assert result.matched_filing is not None
    assert result.status is None


def test_verify_rumour_explain_output_mentions_matched_filing():
    corpus = load_corpus()
    result = verify_rumour(
        "IREDA has declared Gensol Engineering's loan accounts as fraud and reported it to the RBI",
        corpus,
        rumour_date=date(2026, 7, 13),
        evaluated_at=datetime(2026, 7, 15),
    )
    text = result.explain()
    assert "F003" in text
    assert "confirmed" in text
