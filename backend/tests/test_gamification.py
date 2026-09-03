from decimal import Decimal

import pytest

from app.services.gamification import crossed_thresholds, longest_trailing_positive_streak
from app.services.gamification_config import (
    MILESTONE_CATALOG,
    GamificationOutcomeSignalError,
    MilestoneDefinition,
    SignalType,
    _assert_all_effort_signals,
)

# --- crossed_thresholds ---


def test_no_thresholds_crossed_below_the_first():
    result = crossed_thresholds(Decimal("0.5"), (1, 2, 4, 6), set(), lambda t: f"buffer_{t}")
    assert result == []


def test_exact_threshold_value_counts_as_crossed():
    result = crossed_thresholds(Decimal("1"), (1, 2, 4, 6), set(), lambda t: f"buffer_{t}")
    assert result == [(1, "buffer_1")]


def test_a_big_jump_crosses_every_threshold_in_between():
    result = crossed_thresholds(Decimal("8"), (1, 2, 4, 6), set(), lambda t: f"buffer_{t}")
    assert result == [(1, "buffer_1"), (2, "buffer_2"), (4, "buffer_4"), (6, "buffer_6")]


def test_already_awarded_thresholds_are_not_returned_again():
    already = {"buffer_1", "buffer_2"}
    result = crossed_thresholds(Decimal("8"), (1, 2, 4, 6), already, lambda t: f"buffer_{t}")
    assert result == [(4, "buffer_4"), (6, "buffer_6")]


def test_no_new_thresholds_once_everything_is_already_awarded():
    already = {"buffer_1", "buffer_2", "buffer_4", "buffer_6"}
    result = crossed_thresholds(Decimal("8"), (1, 2, 4, 6), already, lambda t: f"buffer_{t}")
    assert result == []


def test_works_with_plain_int_values_too():
    result = crossed_thresholds(3, (1, 3, 5), set(), lambda t: f"n_{t}")
    assert result == [(1, "n_1"), (3, "n_3")]


# --- longest_trailing_positive_streak ---


def test_empty_history_has_zero_streak():
    assert longest_trailing_positive_streak([]) == 0


def test_all_positive_is_the_full_length():
    assert longest_trailing_positive_streak([100, 200, 300]) == 3


def test_stops_at_first_negative_or_zero_walking_backward():
    assert longest_trailing_positive_streak([100, -50, 200, 300]) == 2


def test_trailing_zero_breaks_the_streak():
    assert longest_trailing_positive_streak([100, 200, 0]) == 0


def test_a_dip_in_the_middle_does_not_affect_the_trailing_count():
    assert longest_trailing_positive_streak([-100, 50, 60, 70]) == 3


# --- the effort-only guard, proven to actually fire ---


def test_real_catalog_is_all_effort_signals():
    # if this ever fails, MILESTONE_CATALOG has an outcome-typed entry --
    # which should never happen, since the module already refused to
    # import in that case
    _assert_all_effort_signals(MILESTONE_CATALOG)  # must not raise
    assert all(m.signal_type == SignalType.EFFORT for m in MILESTONE_CATALOG)


def test_guard_actually_rejects_an_outcome_signal():
    from app.services.gamification_config import Category

    poisoned_catalog = MILESTONE_CATALOG + (
        MilestoneDefinition(Category.BUFFER, SignalType.OUTCOME, "portfolio value went up 10% this month"),
    )
    with pytest.raises(GamificationOutcomeSignalError):
        _assert_all_effort_signals(poisoned_catalog)
