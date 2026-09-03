import pytest

from app.services.risk_profile import compute_stated_tier
from app.services.risk_profile_config import QUESTIONNAIRE_V1

ALL_MIN = {"horizon": "lt_1y", "drawdown_reaction": "sell_all", "experience": "none", "goal": "preserve"}
ALL_MAX = {"horizon": "gt_15y", "drawdown_reaction": "buy_a_lot", "experience": "extensive", "goal": "maximize"}
AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
}


def test_questionnaire_weights_sum_to_ten():
    assert sum(q.weight for q in QUESTIONNAIRE_V1.questions) == 10


def test_all_minimum_answers_score_the_floor_and_tier_1():
    result = compute_stated_tier(ALL_MIN)
    assert result.score == 10
    assert result.tier == 1


def test_all_maximum_answers_score_the_ceiling_and_tier_5():
    result = compute_stated_tier(ALL_MAX)
    assert result.score == 50
    assert result.tier == 5


def test_aggressive_answers_hand_checked_score_and_tier():
    # horizon gt_15y=5*3=15, drawdown buy_a_lot=5*3=15,
    # experience significant=4*2=8, goal maximize=5*2=10 -> 48
    result = compute_stated_tier(AGGRESSIVE_ANSWERS)
    assert result.score == 48
    assert result.tier == 5


@pytest.mark.parametrize(
    "score_answers,expected_tier",
    [
        # score exactly at each breakpoint boundary
        ({"horizon": "lt_1y", "drawdown_reaction": "sell_all", "experience": "moderate", "goal": "balanced"}, 2),  # 3+3+6+6=18
    ],
)
def test_breakpoint_boundaries_are_inclusive_on_the_upper_tier(score_answers, expected_tier):
    result = compute_stated_tier(score_answers)
    assert result.score == 18
    assert result.tier == expected_tier


def test_missing_answer_raises_value_error():
    incomplete = dict(ALL_MIN)
    del incomplete["goal"]
    with pytest.raises(ValueError, match="missing answers"):
        compute_stated_tier(incomplete)


def test_unknown_option_value_raises_value_error():
    bad = dict(ALL_MIN)
    bad["goal"] = "not_a_real_option"
    with pytest.raises(ValueError):
        compute_stated_tier(bad)


def test_unknown_question_id_is_ignored_extra_keys_allowed():
    answers = dict(ALL_MIN)
    answers["some_future_question"] = "whatever"
    result = compute_stated_tier(answers)
    assert result.score == 10  # unaffected by the unused extra key
