"""Tests for the explanation-quality harness.

An evaluation nobody tests is an evaluation that can silently start
reporting 1.000 for the wrong reason. These check that each metric can
actually fail -- a metric that cannot fail measures nothing -- and pin
the properties the project's explainability claim rests on.
"""

from datetime import date

import pytest

from eval.evaluate_explanations import (
    CONSTRAINTS,
    ExplanationMetrics,
    evaluate_explanations,
    expected_failed_constraints,
    format_report,
)
from src.corpus import load_corpus, load_rumour_dataset


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture(scope="module")
def dataset():
    return load_rumour_dataset()


@pytest.fixture(scope="module")
def metrics(corpus, dataset):
    return evaluate_explanations(corpus, dataset)


def test_the_score_floor_is_one_of_the_evaluated_reasons():
    """The floor eliminates candidates, so it must be scored. It was
    originally absent from the trace, and that absence is what the
    sufficiency metric caught."""
    assert "score_floor" in CONSTRAINTS


def test_every_candidate_considered_receives_an_explanation(metrics):
    assert metrics.candidates_considered > 0
    assert metrics.coverage == 1.0
    assert metrics.reason_coverage == 1.0


def test_the_verdict_can_be_reproduced_from_the_trace_alone(metrics):
    """The strongest property: the explanation is the reason for the answer,
    not a story told alongside it. If this drops below 1.0, some candidate
    is being eliminated by something the trace does not disclose."""
    assert metrics.sufficiency == 1.0


def test_every_winner_ranked_first_claim_holds(metrics):
    assert metrics.winner_soundness == 1.0


def test_no_elimination_is_claimed_that_is_not_independently_true(metrics):
    """Precision must be perfect: the trace may under-report (see the entity
    no-op finding) but must never assert an elimination that did not happen."""
    for constraint in CONSTRAINTS:
        counts = metrics.per_constraint[constraint]
        assert counts.precision == 1.0, f"{constraint} claims eliminations that are not real"


def test_temporal_source_and_floor_checks_are_exactly_right(metrics):
    for constraint in ("temporal", "source_authority", "score_floor"):
        counts = metrics.per_constraint[constraint]
        assert counts.recall == 1.0, f"{constraint} recall regressed"


def test_the_known_entity_no_op_is_still_the_only_shortfall(metrics):
    """Pins the documented finding. If entity recall reaches 1.0 someone
    fixed `mentioned_companies`, and the report's 'known finding' section
    should be removed rather than left claiming a defect that is gone."""
    assert metrics.per_constraint["entity"].recall < 1.0
    assert all("entity" in d for d in metrics.disagreements)


def test_ground_truth_is_computed_independently_of_the_system(corpus, dataset):
    """The ground-truth helper must be derivable from the dataset label and
    the filing alone -- if it consulted the retriever, agreement would be
    tautological."""
    case = dataset[0]
    wrong_company = next(f for f in corpus if f.company_name != case.company_name)
    failed = expected_failed_constraints(wrong_company, case, score=1.0, min_score=0.08)
    assert "entity" in failed

    stale = next(f for f in corpus if (f.filing_date - case.rumour_date).days > 30)
    assert "temporal" in expected_failed_constraints(stale, case, score=1.0, min_score=0.08)

    assert "score_floor" in expected_failed_constraints(
        corpus[0], case, score=0.001, min_score=0.08
    )


def test_metrics_can_actually_fail():
    """A metric that cannot report a failure is not measuring anything."""
    empty = ExplanationMetrics()
    empty.queries = 2
    empty.candidates_considered = 10
    empty.candidates_explained = 5  # half the candidates went unexplained
    empty.sufficiency_checked = 2
    empty.sufficiency_reproduced = 1

    assert empty.coverage == 0.5
    assert empty.sufficiency == 0.5


def test_report_lists_disagreements_rather_than_hiding_them(metrics, dataset):
    report = format_report(metrics, dataset)
    assert "## Disagreements" in report
    assert "Verdict sufficiency" in report
    assert "R005" in report  # the grouped finding is named, not summarized away


def test_report_never_claims_ai(metrics, dataset):
    report = format_report(metrics, dataset).lower()
    assert "explainable ai" not in report
    assert "ai-powered" not in report
    assert "artificial intelligence" not in report
