"""Module 10: versioned milestone catalog and thresholds.

HARD RULE, ENFORCED HERE AT IMPORT TIME, NOT JUST DOCUMENTED: every
milestone rewards an EFFORT signal (a contribution, an action taken, a
consistency streak) and NEVER an OUTCOME signal (market returns, holding
or portfolio value change). Conflating the two is a bug, not a style
choice — see `SignalType` and `_assert_all_effort_signals` below, which
runs the instant this module is imported. A future contributor adding an
outcome-typed milestone to `MILESTONE_CATALOG` doesn't get a code-review
comment; the app fails to start.

Concretely, this module never reads Module 4's `current_exposure_paise`,
`current_exposure_pct`, or `total_value_paise` (portfolio value / market
exposure), and never will — every signal below comes from Module 2's own
declared inputs (buffer months, EMI principal, expense line items,
monthly surplus) or Module 3's rule-table output (capacity ceiling), none
of which move because a market did.

Hard exclusions (also enforced structurally, not just by omission): no
leaderboard or cross-user comparison — every function in this module
takes exactly one `user_id` and never queries across users. No streak for
merely opening the app — this module has no access to any "app opened"
event type in Module 1's schema in the first place, and never will.
"""

from dataclasses import dataclass
from enum import Enum

CONFIG_VERSION = "v1"
CONFIG_EFFECTIVE_DATE = "2026-01-01"

# Buffer-month milestones deliberately reuse Module 3's own capacity rule
# table band edges (see risk_profile_config.py), rather than introducing a
# second, potentially-drifting set of "meaningful" buffer thresholds.
BUFFER_MONTHS_THRESHOLDS: tuple[int, ...] = (1, 2, 4, 6)

SUBSCRIPTION_CANCELLED_COUNT_THRESHOLDS: tuple[int, ...] = (1, 3, 5)
CONSISTENCY_MONTH_THRESHOLDS: tuple[int, ...] = (3, 6, 12)


class SignalType(str, Enum):
    EFFORT = "effort"
    OUTCOME = "outcome"  # exists only so the import-time guard has something to reject; no real milestone may use this


class Category(str, Enum):
    BUFFER = "buffer"
    CAPACITY_UNLOCK = "capacity_unlock"  # the one "real" progression mechanic -- see module docstring
    DEBT = "debt"
    SUBSCRIPTIONS = "subscriptions"
    CONSISTENCY = "consistency"


@dataclass(frozen=True)
class MilestoneDefinition:
    category: Category
    signal_type: SignalType
    description: str


# One entry per *category* (not per threshold instance -- individual
# thresholds are generated at detection time from the tuples above). This
# is the thing _assert_all_effort_signals checks.
MILESTONE_CATALOG: tuple[MilestoneDefinition, ...] = (
    MilestoneDefinition(
        Category.BUFFER, SignalType.EFFORT,
        "Emergency-buffer months reached a new threshold -- built from Module 2's own declared cash/expenses.",
    ),
    MilestoneDefinition(
        Category.CAPACITY_UNLOCK, SignalType.EFFORT,
        "Module 3's capacity ceiling rose -- the underlying cause is always an effort signal (more buffer, "
        "lower EMI burden, more insurance cover, or income becoming regular), never a market outcome.",
    ),
    MilestoneDefinition(
        Category.DEBT, SignalType.EFFORT,
        "All EMI debt closed (via Module 2's close_emi) -- an action taken, not a balance that happened to rise.",
    ),
    MilestoneDefinition(
        Category.SUBSCRIPTIONS, SignalType.EFFORT,
        "A recurring, subscription-like expense item was explicitly removed (Module 2's remove_expense_item) "
        "-- an action taken in response to Module 6's leak detection, not an automatic saving.",
    ),
    MilestoneDefinition(
        Category.CONSISTENCY, SignalType.EFFORT,
        "Consecutive months of positive surplus -- a cash-flow discipline signal, not a return.",
    ),
)


class GamificationOutcomeSignalError(RuntimeError):
    pass


def _assert_all_effort_signals(catalog: tuple[MilestoneDefinition, ...]) -> None:
    offending = [m.category.value for m in catalog if m.signal_type != SignalType.EFFORT]
    if offending:
        raise GamificationOutcomeSignalError(
            f"milestone categor(y/ies) {offending} declare a non-effort signal_type. Outcome-based "
            "milestones (market returns, portfolio/holding value change) are a bug in this module, not "
            "a style choice -- see gamification_config.py's module docstring before changing this."
        )


_assert_all_effort_signals(MILESTONE_CATALOG)
