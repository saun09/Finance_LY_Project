import pytest

from app.services.risk_profile import compute_stated_tier
from app.services.risk_profile_config import QUESTIONNAIRE_V1, QUESTIONNAIRE_V2

ALL_MIN_V2 = {
    "horizon": "lt_1y",
    "drawdown_reaction": "sell_all",
    "experience": "none",
    "goal": "preserve",
    "windfall_allocation": "fd_or_savings",
    "sure_gain_tradeoff": "guaranteed_5000",
    "friend_description": "real_risk_avoider",
}
ALL_MAX_V2 = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "extensive",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
}

ALL_MIN = {"horizon": "lt_1y", "drawdown_reaction": "sell_all", "experience": "none", "goal": "preserve"}
ALL_MAX = {"horizon": "gt_15y", "drawdown_reaction": "buy_a_lot", "experience": "extensive", "goal": "maximize"}
AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
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


# --- QUESTIONNAIRE_V2 (7 questions, total weight 20, score range [20, 100]) ---


def test_v2_questionnaire_weights_sum_to_twenty():
    assert sum(q.weight for q in QUESTIONNAIRE_V2.questions) == 20
    assert QUESTIONNAIRE_V2.min_score == 20
    assert QUESTIONNAIRE_V2.max_score == 100


def test_v2_all_minimum_answers_score_the_floor_and_tier_1():
    result = compute_stated_tier(ALL_MIN_V2, QUESTIONNAIRE_V2)
    assert result.score == 20
    assert result.tier == 1


def test_v2_all_maximum_answers_score_the_ceiling_and_tier_5():
    result = compute_stated_tier(ALL_MAX_V2, QUESTIONNAIRE_V2)
    assert result.score == 100
    assert result.tier == 5


@pytest.mark.parametrize(
    "score_answers,expected_score,expected_tier",
    [
        # baseline is ALL_MIN_V2 = score 20 (weights: horizon=3,
        # drawdown_reaction=3, experience=2, goal=2, windfall_allocation=4,
        # sure_gain_tradeoff=4, friend_description=2; sum=20). Each override
        # below adds weight*(points-1) on top of that floor of 20.

        # breakpoint 1 (36): only sure_gain_tradeoff maxed -> 20 + 4*4 = 36
        ({**ALL_MIN_V2, "sure_gain_tradeoff": "chance_10pct_50000"}, 36, 2),
        # breakpoint 2 (52): sure_gain_tradeoff + windfall_allocation maxed
        # -> 20 + 4*4 + 4*4 = 52
        (
            {**ALL_MIN_V2, "sure_gain_tradeoff": "chance_10pct_50000", "windfall_allocation": "equity_plus_borrow"},
            52,
            3,
        ),
        # breakpoint 3 (68): horizon + windfall_allocation + sure_gain_tradeoff
        # maxed (12+16+16=44), plus friend_description at its middle option
        # (points=3, weight2*(3-1)=4) -> 20 + 44 + 4 = 68
        (
            {
                **ALL_MIN_V2,
                "horizon": "gt_15y",
                "windfall_allocation": "equity_plus_borrow",
                "sure_gain_tradeoff": "chance_10pct_50000",
                "friend_description": "calculated_after_research",
            },
            68,
            4,
        ),
        # breakpoint 4 (84): everything maxed except windfall_allocation left
        # at its floor -> 20 + (80 - 4*4) = 20 + 64 = 84
        ({**ALL_MAX_V2, "windfall_allocation": "fd_or_savings"}, 84, 5),
    ],
)
def test_v2_breakpoint_boundaries_are_inclusive_on_the_upper_tier(score_answers, expected_score, expected_tier):
    result = compute_stated_tier(score_answers, QUESTIONNAIRE_V2)
    assert result.score == expected_score
    assert result.tier == expected_tier
