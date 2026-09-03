"""Module 7: pure personalization-offset logic. No I/O, no model call.

The offset is a single number, in equity percentage points, meant to
nudge Module 4's *displayed* target allocation toward what a user's own
behavior has shown they actually want — without ever touching Module 3's
risk tier, and never past what Module 3's capacity ceiling allows. It is
derived by replaying the user's suggestion_event history through an
evidence-weighted EWMA (see compute_offset_from_edits) rather than stored
as its own row anywhere — same "no new state table, replay the event log"
pattern Modules 3/4/6 already use, which keeps the offset always exactly
reproducible from Module 1's log.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from app.services.asset_classification_config import AssetClass

OFFSET_MIN = Decimal("-10")
OFFSET_MAX = Decimal("10")

# Default smoothing parameter. With weight=1 (a funded edit), the fraction
# of the *old* estimate remaining after n consecutive full-weight
# observations is (1-alpha)^n: 70% after 1, ~34% after 3, ~8% after 7. A
# single edit therefore only nudges the offset 30% of the way toward that
# one data point (real resistance to a one-off/mistaken edit), while a
# consistent pattern across 5-7 interactions dominates the estimate --
# fast enough to feel like a "fast feedback loop" within a first week of
# real use, without overreacting to any single event. Zero-weight events
# (rejections, "confusion") are exact no-ops regardless of alpha, by
# construction (see compute_offset_from_edits).
DEFAULT_ALPHA = Decimal("0.3")


class EditActionTaken(str, Enum):
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    IGNORED = "ignored"


def evidence_weight(action_taken: EditActionTaken, funded: bool | None) -> Decimal:
    """Named in the module brief: a funded edit is full weight (1.0), an
    unfunded acceptance is half weight (0.5), a rejection ("confusion") is
    zero. The remaining action_taken x funded combinations aren't named
    explicitly, so they're extrapolated from the same two factors the
    named cases already turn on:

    - Does the action carry a directional preference at all? ACCEPTED and
      EDITED both do (accepting confirms the suggestion as offered;
      editing states a specific alternative). REJECTED and IGNORED don't
      -- neither tells us what the user *would* want, only that this
      suggestion wasn't it (or wasn't engaged with), so both are zero
      regardless of `funded`.
    - Was it actually followed through on? `funded=True` is full
      conviction (1.0). `funded=False` -- or `None`, meaning follow-through
      is simply unknown -- gets the same conservative half weight as the
      named "unfunded acceptance" case, since neither is positive
      confirmation.
    """
    if action_taken in (EditActionTaken.REJECTED, EditActionTaken.IGNORED):
        return Decimal("0")
    return Decimal("1") if funded else Decimal("0.5")


@dataclass(frozen=True)
class AllocationEdit:
    suggested_equity_pct: Decimal
    chosen_equity_pct: Decimal | None  # None when nothing was explicitly chosen (e.g. a plain accept/reject)
    action_taken: EditActionTaken
    funded: bool | None


def _delta_for(edit: AllocationEdit) -> Decimal:
    if edit.chosen_equity_pct is None:
        return Decimal("0")
    return edit.chosen_equity_pct - edit.suggested_equity_pct


def _clamp(value: Decimal) -> Decimal:
    return max(OFFSET_MIN, min(OFFSET_MAX, value))


@dataclass(frozen=True)
class OffsetStep:
    step: int
    weight: Decimal
    delta_pct: Decimal
    offset_before: Decimal
    offset_after: Decimal


def compute_offset_from_edits(
    edits: list[AllocationEdit], alpha: Decimal = DEFAULT_ALPHA, start: Decimal = Decimal("0")
) -> tuple[Decimal, list[OffsetStep]]:
    """Replay a chronological sequence of allocation edits through the
    evidence-weighted EWMA: offset_new = (1 - alpha*weight)*offset_old +
    (alpha*weight)*delta. When weight is 0, this is an exact no-op --
    zero-weight evidence doesn't decay the running estimate at all, it's
    simply skipped, matching "counts zero" literally rather than injecting
    a hidden pull toward zero.
    """
    offset = _clamp(start)
    trace: list[OffsetStep] = []
    for i, edit in enumerate(edits, start=1):
        weight = evidence_weight(edit.action_taken, edit.funded)
        delta = _delta_for(edit)
        effective_alpha = alpha * weight
        new_offset = _clamp((1 - effective_alpha) * offset + effective_alpha * delta)
        trace.append(OffsetStep(step=i, weight=weight, delta_pct=delta, offset_before=offset, offset_after=new_offset))
        offset = new_offset
    return offset, trace


def apply_personalization_offset(
    target_pct: dict[AssetClass, Decimal],
    capacity_ceiling_target_pct: dict[AssetClass, Decimal],
    offset_pct_points: Decimal,
) -> dict[AssetClass, Decimal]:
    """Apply the offset to Module 4's target allocation for display only.

    `target_pct` is Module 4's target for the user's *final* tier.
    `capacity_ceiling_target_pct` is Module 4's target for the user's
    capacity *ceiling* tier (ability, not the possibly-lower final tier) --
    its equity share is the hard cap the offset can never push past, per
    the module brief. The risk tier itself is never touched by any of
    this; only the displayed percentages move.

    The other four classes absorb whatever the equity change is, scaled
    proportionally to their own current weights, so the result always sums
    to exactly 100.00.
    """
    base_equity = target_pct[AssetClass.EQUITY]
    max_equity_allowed = capacity_ceiling_target_pct[AssetClass.EQUITY]

    naive_equity = base_equity + offset_pct_points
    capped_equity = max(Decimal("0"), min(naive_equity, max_equity_allowed, Decimal("100")))

    other_classes = [c for c in AssetClass if c != AssetClass.EQUITY]
    other_original_sum = sum(target_pct[c] for c in other_classes)
    remaining_pool = Decimal("100") - capped_equity

    if other_original_sum > 0:
        adjusted = {c: (target_pct[c] * remaining_pool / other_original_sum) for c in other_classes}
    else:
        # not reachable with the current allocation table (equity never
        # reaches 100%), guarded anyway rather than dividing by zero
        adjusted = {c: (remaining_pool / len(other_classes)) for c in other_classes}

    result = {AssetClass.EQUITY: capped_equity.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)}
    for c, v in adjusted.items():
        result[c] = v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Any rounding residual is absorbed by the largest of the *other* four
    # classes only -- equity must stay exactly at the capped value computed
    # above, or a rounding artifact could silently push it a cent past the
    # capacity ceiling this function exists to enforce.
    residual = Decimal("100.00") - sum(result.values())
    if residual != 0:
        largest_other = max(other_classes, key=lambda c: result[c])
        result[largest_other] += residual

    return result
