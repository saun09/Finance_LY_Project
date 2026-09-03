"""Standalone demo: replays a synthetic sequence of allocation edits
through Module 7's evidence-weighted EWMA and shows the personalization
offset converging, then applies it to a sample Module 4 allocation with
Module 3's capacity cap reapplied.

No database, no other module's live computation needed -- every input is
constructed in-memory, shaped like what Module 1's event log would hand
Module 7 in a real run (a suggested equity %, a chosen equity % (or None),
an action_taken, and a funded flag). Run with:

    python -m scripts.personalization_demo
"""

from decimal import Decimal

from app.services.allocation_config import TARGET_ALLOCATION_TABLE_V1
from app.services.asset_classification_config import AssetClass
from app.services.personalization import (
    DEFAULT_ALPHA,
    AllocationEdit,
    EditActionTaken,
    apply_personalization_offset,
    compute_offset_from_edits,
)

SUGGESTED_EQUITY_PCT = Decimal("35")  # what Module 4 suggested (tier 3 baseline)

# A synthetic user who consistently wants more equity than suggested, with
# realistic noise along the way: a rejection (should be a pure no-op) and
# an unfunded acceptance (should nudge gently toward "no change needed").
SYNTHETIC_EDITS = [
    AllocationEdit(SUGGESTED_EQUITY_PCT, Decimal("45"), EditActionTaken.EDITED, funded=True),
    AllocationEdit(SUGGESTED_EQUITY_PCT, Decimal("48"), EditActionTaken.EDITED, funded=True),
    AllocationEdit(SUGGESTED_EQUITY_PCT, None, EditActionTaken.REJECTED, funded=None),  # "confusion" -- must be a no-op
    AllocationEdit(SUGGESTED_EQUITY_PCT, None, EditActionTaken.ACCEPTED, funded=False),  # unfunded acceptance -- gentle pull to 0
    AllocationEdit(SUGGESTED_EQUITY_PCT, Decimal("50"), EditActionTaken.EDITED, funded=True),
    AllocationEdit(SUGGESTED_EQUITY_PCT, Decimal("47"), EditActionTaken.EDITED, funded=True),
]


def main() -> None:
    print(f"Suggested equity: {SUGGESTED_EQUITY_PCT}%   alpha={DEFAULT_ALPHA} (see personalization.py for why)\n")

    offset, trace = compute_offset_from_edits(SYNTHETIC_EDITS, alpha=DEFAULT_ALPHA)

    print(f"{'step':>4} {'action':<10} {'funded':<7} {'weight':>6} {'delta%':>7} {'offset before':>14} {'offset after':>13}")
    for step, edit in zip(trace, SYNTHETIC_EDITS):
        print(
            f"{step.step:>4} {edit.action_taken.value:<10} {str(edit.funded):<7} "
            f"{step.weight:>6} {step.delta_pct:>7} {step.offset_before:>14} {step.offset_after:>13}"
        )

    print(f"\nConverged offset after {len(SYNTHETIC_EDITS)} edits: {offset:+} percentage points")

    # Apply to a sample tier-3 allocation. Capacity ceiling == final tier
    # here (3), so the offset's own upward pull (+9.249) pushes past what
    # ability allows (35%) -- deliberately chosen so the demo actually
    # shows the cap binding, not just a case where it never comes up.
    final_tier, capacity_ceiling = 3, 3
    base = TARGET_ALLOCATION_TABLE_V1[final_tier]
    ceiling_target = TARGET_ALLOCATION_TABLE_V1[capacity_ceiling]
    displayed = apply_personalization_offset(base, ceiling_target, offset)

    print(f"\nFinal tier stays {final_tier} (personalization never touches the tier).")
    print(f"Capacity ceiling stays {capacity_ceiling}; its equity share ({ceiling_target[AssetClass.EQUITY]}%) is the hard cap.")
    naive_equity = base[AssetClass.EQUITY] + offset
    print(f"Naive equity (base {base[AssetClass.EQUITY]}% + offset {offset:+}) would be {naive_equity}% -- capped to {displayed[AssetClass.EQUITY]}%.")
    print(f"\n{'class':<14} {'base %':>8} {'displayed %':>12}")
    for ac in AssetClass:
        print(f"{ac.value:<14} {base[ac]:>8} {displayed[ac]:>12}")
    print(f"\nDisplayed allocation sums to {sum(displayed.values())}%.")

    print("\n--- now with a generous capacity ceiling (tier 5), same offset ---")
    generous_ceiling = TARGET_ALLOCATION_TABLE_V1[5]
    generous_displayed = apply_personalization_offset(base, generous_ceiling, offset)
    print(f"Capacity ceiling's equity share: {generous_ceiling[AssetClass.EQUITY]}% -- not binding this time.")
    print(f"Displayed equity: {generous_displayed[AssetClass.EQUITY]}% (the offset's full effect, uncapped).")


if __name__ == "__main__":
    main()
