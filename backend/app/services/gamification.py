"""Module 10: pure milestone-detection helpers. No I/O, no model call —
plain functions over values a caller has already fetched, in the same
spirit as every other deterministic module in this project.
"""

from collections.abc import Callable
from decimal import Decimal


def crossed_thresholds(
    current_value: Decimal | int,
    thresholds: tuple[int, ...],
    already_awarded_ids: set[str],
    id_fn: Callable[[int], str],
) -> list[tuple[int, str]]:
    """Which thresholds are newly earned, as (threshold_value, milestone_id)
    pairs: the current value has reached or passed the threshold, and that
    specific threshold's id hasn't already been awarded. Order follows
    `thresholds` so a caller processing a big jump (e.g. buffer going from
    0 to 8 months in one edit) awards every threshold it actually crossed,
    not just the highest one. Returning the threshold value alongside the
    id avoids callers having to parse it back out of the id string."""
    return [(t, id_fn(t)) for t in thresholds if current_value >= t and id_fn(t) not in already_awarded_ids]


def longest_trailing_positive_streak(values_oldest_to_newest: list[int]) -> int:
    """How many consecutive periods, counting back from the most recent,
    have been strictly positive. Stops at the first non-positive value
    encountered walking backward from the end."""
    streak = 0
    for v in reversed(values_oldest_to_newest):
        if v > 0:
            streak += 1
        else:
            break
    return streak
