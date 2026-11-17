import numpy as np

from app.services.risk_profile_config import QUESTIONNAIRE_V2
from research_artifacts.experiments.convergent_validity import (
    bootstrap_correlation_interval,
    cronbach_alpha,
    load_aligned_rows,
    parse_self_rating,
    _score_rows,
)


def test_self_rating_parser_accepts_only_numeric_values_in_range():
    assert parse_self_rating(0) == (0.0, None)
    assert parse_self_rating("10") == (10.0, None)
    assert parse_self_rating(None) == (None, "missing")
    assert parse_self_rating("not answered") == (None, "non_numeric")
    assert parse_self_rating(True) == (None, "non_numeric")
    assert parse_self_rating(10.1) == (None, "out_of_range")
    assert parse_self_rating(-0.1) == (None, "out_of_range")


def test_cronbach_alpha_returns_one_for_identical_item_columns():
    values = np.asarray(
        [
            [1, 1, 1],
            [2, 2, 2],
            [3, 3, 3],
            [4, 4, 4],
        ],
        dtype=float,
    )

    assert cronbach_alpha(values) == 1.0


def test_bootstrap_correlation_interval_is_reproducible():
    x = np.arange(20, dtype=float)
    y = x.copy()

    first = bootstrap_correlation_interval(x, y, "spearman", seed=29, n_resamples=200)
    second = bootstrap_correlation_interval(x, y, "spearman", seed=29, n_resamples=200)

    assert first == second
    assert first[0] <= 1 <= first[1]


def test_reduced_model_receives_only_four_mapped_items_not_self_rating():
    answers = {
        question.id: question.options[0].value
        for question in QUESTIONNAIRE_V2.questions
    }

    class CaptureModel:
        received = None

        def predict(self, model_inputs):
            self.received = model_inputs.copy()
            return np.asarray([1])

    model = CaptureModel()
    _, measures = _score_rows([{"answers": answers, "self_rating": 10.0}], model)

    assert model.received.shape == (1, 4)
    assert "self_rating" not in measures
    assert set(measures) == {
        "weighted_score",
        "stated_tier",
        "reduced_rf_tier",
        *(question.id for question in QUESTIONNAIRE_V2.questions),
    }


def test_workbook_self_rating_rows_remain_aligned_with_canonical_mapped_answers():
    rows, accounting = load_aligned_rows()

    assert len(rows) == accounting["mapped_rows_with_valid_self_rating"]
    assert len({row["excel_row"] for row in rows}) == len(rows)
    assert all(0 <= row["self_rating"] <= 10 for row in rows)
    assert all(set(row["answers"]) == {question.id for question in QUESTIONNAIRE_V2.questions} for row in rows)
    assert all(
        parse_self_rating(row["raw_row"][accounting["rating_column_index_zero_based"]])[0]
        == row["self_rating"]
        for row in rows
    )
