from decimal import Decimal

import pytest

from app.services.asset_classification_config import AssetClass
from app.services.personalization import (
    OFFSET_MAX,
    OFFSET_MIN,
    AllocationEdit,
    EditActionTaken,
    apply_personalization_offset,
    compute_offset_from_edits,
    evidence_weight,
)

ACCEPTED = EditActionTaken.ACCEPTED
EDITED = EditActionTaken.EDITED
REJECTED = EditActionTaken.REJECTED
IGNORED = EditActionTaken.IGNORED


# --- evidence weight ---


def test_named_weight_cases_from_the_brief():
    assert evidence_weight(EDITED, funded=True) == Decimal("1")  # funded edit
    assert evidence_weight(ACCEPTED, funded=False) == Decimal("0.5")  # unfunded acceptance
    assert evidence_weight(REJECTED, funded=True) == Decimal("0")  # rejection ("confusion")
    assert evidence_weight(REJECTED, funded=False) == Decimal("0")
    assert evidence_weight(REJECTED, funded=None) == Decimal("0")


def test_ignored_is_also_zero_weight():
    assert evidence_weight(IGNORED, funded=True) == Decimal("0")
    assert evidence_weight(IGNORED, funded=None) == Decimal("0")


def test_unfunded_edit_and_unknown_funded_get_half_weight():
    assert evidence_weight(EDITED, funded=False) == Decimal("0.5")
    assert evidence_weight(EDITED, funded=None) == Decimal("0.5")
    assert evidence_weight(ACCEPTED, funded=None) == Decimal("0.5")


def test_funded_acceptance_is_full_weight():
    assert evidence_weight(ACCEPTED, funded=True) == Decimal("1")


# --- EWMA trajectory, hand-checked ---


def test_single_funded_edit_moves_offset_thirty_percent_of_the_way():
    # alpha=0.3, weight=1 -> effective_alpha=0.3
    # offset = 0.7*0 + 0.3*15 = 4.5
    edits = [AllocationEdit(Decimal("35"), Decimal("50"), EDITED, funded=True)]
    offset, trace = compute_offset_from_edits(edits)
    assert offset == Decimal("4.500")
    assert trace[0].weight == Decimal("1")
    assert trace[0].delta_pct == Decimal("15")


def test_repeated_consistent_funded_edits_converge_toward_and_clamp_at_max():
    # delta=15 every time (exceeds the +10 band), alpha=0.3, weight=1
    # step1: 0.7*0 + 0.3*15 = 4.5
    # step2: 0.7*4.5 + 0.3*15 = 7.65
    # step3: 0.7*7.65 + 0.3*15 = 9.855
    # step4: 0.7*9.855 + 0.3*15 = 11.3985 -> clamped to 10
    edits = [AllocationEdit(Decimal("35"), Decimal("50"), EDITED, funded=True)] * 4
    offset, trace = compute_offset_from_edits(edits)
    assert [s.offset_after for s in trace[:3]] == [Decimal("4.500"), Decimal("7.6500"), Decimal("9.85500")]
    assert offset == OFFSET_MAX


def test_rejection_is_an_exact_no_op():
    edits = [
        AllocationEdit(Decimal("35"), Decimal("50"), EDITED, funded=True),  # -> 4.5
        AllocationEdit(Decimal("35"), None, REJECTED, funded=None),  # no-op
    ]
    offset, trace = compute_offset_from_edits(edits)
    assert trace[0].offset_after == Decimal("4.500")
    assert trace[1].offset_after == trace[0].offset_after  # completely unchanged
    assert offset == Decimal("4.500")


def test_unfunded_acceptance_pulls_gently_toward_zero():
    # starting from 4.5, an unfunded acceptance has delta=0, weight=0.5,
    # effective_alpha=0.15 -> 0.85*4.5 + 0.15*0 = 3.825
    edits = [
        AllocationEdit(Decimal("35"), Decimal("50"), EDITED, funded=True),
        AllocationEdit(Decimal("35"), None, ACCEPTED, funded=False),
    ]
    offset, trace = compute_offset_from_edits(edits)
    assert trace[1].offset_after == Decimal("3.8250")


def test_offset_never_exceeds_bounds_even_with_extreme_deltas():
    edits = [AllocationEdit(Decimal("35"), Decimal("100"), EDITED, funded=True)] * 20
    offset, _ = compute_offset_from_edits(edits)
    assert offset == OFFSET_MAX

    edits_negative = [AllocationEdit(Decimal("35"), Decimal("0"), EDITED, funded=True)] * 20
    offset_negative, _ = compute_offset_from_edits(edits_negative)
    assert offset_negative == OFFSET_MIN


def test_alpha_is_configurable_and_changes_convergence_speed():
    edits = [AllocationEdit(Decimal("35"), Decimal("50"), EDITED, funded=True)]
    slow_offset, _ = compute_offset_from_edits(edits, alpha=Decimal("0.1"))
    fast_offset, _ = compute_offset_from_edits(edits, alpha=Decimal("0.5"))
    assert slow_offset < fast_offset


def test_empty_edit_history_leaves_offset_at_zero():
    offset, trace = compute_offset_from_edits([])
    assert offset == Decimal("0")
    assert trace == []


# --- applying the offset with capacity reapplication ---


def _tier3_target():
    return {
        AssetClass.CASH: Decimal("15"),
        AssetClass.DEBT: Decimal("40"),
        AssetClass.EQUITY: Decimal("35"),
        AssetClass.REAL_ASSETS: Decimal("8"),
        AssetClass.ALTERNATIVES: Decimal("2"),
    }


def _tier5_target():
    return {
        AssetClass.CASH: Decimal("5"),
        AssetClass.DEBT: Decimal("15"),
        AssetClass.EQUITY: Decimal("65"),
        AssetClass.REAL_ASSETS: Decimal("10"),
        AssetClass.ALTERNATIVES: Decimal("5"),
    }


def test_positive_offset_within_capacity_shifts_equity_up():
    result = apply_personalization_offset(_tier3_target(), _tier5_target(), Decimal("8"))
    assert result[AssetClass.EQUITY] == Decimal("43.00")  # 35 + 8, well under the tier-5 cap of 65
    assert sum(result.values()) == Decimal("100.00")


def test_offset_is_capped_at_the_capacity_ceilings_equity_share():
    # final tier's own target is 35% equity; capacity ceiling (ability)
    # only permits up to 65% (tier 5's target) even before considering the
    # offset's own [-10,+10] bound
    same_tier_ceiling = _tier3_target()  # capacity ceiling == final tier: max allowed is 35
    result = apply_personalization_offset(_tier3_target(), same_tier_ceiling, Decimal("10"))
    # naive would be 35+10=45, but capacity ceiling here only allows 35
    assert result[AssetClass.EQUITY] == Decimal("35.00")


def test_offset_still_bounded_by_own_clamp_even_when_capacity_is_generous():
    # offset itself is passed in already clamped by compute_offset_from_edits,
    # but this checks apply_personalization_offset doesn't rely on that --
    # a wildly out-of-range offset is still capped at the capacity ceiling
    result = apply_personalization_offset(_tier3_target(), _tier5_target(), Decimal("50"))
    assert result[AssetClass.EQUITY] == Decimal("65.00")  # capped at capacity ceiling's equity share


def test_negative_offset_is_not_constrained_by_capacity_ceiling():
    result = apply_personalization_offset(_tier3_target(), _tier5_target(), Decimal("-10"))
    assert result[AssetClass.EQUITY] == Decimal("25.00")  # 35 - 10, capacity ceiling irrelevant here


def test_other_classes_rescale_proportionally_and_sum_stays_100():
    base = _tier3_target()
    result = apply_personalization_offset(base, _tier5_target(), Decimal("5"))
    assert sum(result.values()) == Decimal("100.00")
    # relative proportions among the other four classes should be preserved
    original_ratio = base[AssetClass.DEBT] / base[AssetClass.CASH]
    new_ratio = result[AssetClass.DEBT] / result[AssetClass.CASH]
    assert abs(original_ratio - new_ratio) < Decimal("0.01")


def test_zero_offset_returns_the_original_target_unchanged():
    base = _tier3_target()
    result = apply_personalization_offset(base, _tier5_target(), Decimal("0"))
    assert result[AssetClass.EQUITY] == base[AssetClass.EQUITY]
    for c in AssetClass:
        assert abs(result[c] - base[c]) < Decimal("0.01")
