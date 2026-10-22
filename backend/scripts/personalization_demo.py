"""Module 7 demo, in two parts. Run with:

    python -m scripts.personalization_demo

Part 1 -- the arithmetic alone. Replays a synthetic sequence of choices
through the evidence-weighted EWMA and shows the offset converging. No
database.

Part 2 -- one live session through the real services, on a throwaway
in-memory database: Module 3 tiers a user, Module 4 shows an allocation,
the user responds to that exact suggestion five times (edit, edit not yet
invested, reject out of confusion, accept, later "I've invested it"), and
each new allocation is built from everything recorded so far. Then the
same loop for a user whose capacity cap binds, and the Module 9 trace that
explains every step. This is the "can be demonstrated in a single session"
claim, exercised end to end rather than asserted.
"""

import sys
from decimal import Decimal

from sqlalchemy.orm import Session

import app.models  # noqa: F401 -- registers models on Base.metadata
from app.db import Base, make_engine
from app.models.onboarding import EmploymentType, IncomeStability
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import AssetClass, HoldingType
from app.services.financial_position import ExpenseFrequency
from app.services.onboarding import add_expense_item, add_holding, upsert_profile
from app.services.personalization import DEFAULT_ALPHA, AllocationEdit, EditActionTaken, compute_offset_from_edits
from app.services.personalization_service import compute_and_log_personalization, mark_allocation_funded, record_allocation_outcome
from app.services.risk_profile_service import compute_and_log_risk_tier
from app.services.transparency import get_trace
from app.services.transparency_labels import constraint_label

# --- Part 1 ----------------------------------------------------------------

BASE_EQUITY_PCT = Decimal("31")  # tier 3's base target

# Every chosen % is measured against the tier's *base* target. An accept
# records what was displayed (base + the offset at that moment), so it
# confirms the current offset rather than pulling it back to zero.
SYNTHETIC_EDITS = [
    AllocationEdit(BASE_EQUITY_PCT, Decimal("41"), EditActionTaken.EDITED, funded=True),
    AllocationEdit(BASE_EQUITY_PCT, Decimal("44"), EditActionTaken.EDITED, funded=True),
    AllocationEdit(BASE_EQUITY_PCT, None, EditActionTaken.REJECTED, funded=None, reason_code="dont_understand"),
    AllocationEdit(BASE_EQUITY_PCT, Decimal("37"), EditActionTaken.ACCEPTED, funded=False),  # displayed was 31 + 6.00
    AllocationEdit(BASE_EQUITY_PCT, Decimal("43"), EditActionTaken.EDITED, funded=True),
]


def part_1() -> None:
    print("=" * 78)
    print("PART 1 -- the EWMA on its own")
    print("=" * 78)
    print(f"Tier's base equity: {BASE_EQUITY_PCT}%   alpha={DEFAULT_ALPHA}\n")
    offset, trace = compute_offset_from_edits(SYNTHETIC_EDITS, alpha=DEFAULT_ALPHA)
    print(f"{'step':>4} {'action':<9} {'reason':<16} {'funded':<7} {'weight':>6} {'delta':>7} {'offset':>18}")
    for step in trace:
        print(
            f"{step.step:>4} {step.action_taken.value:<9} {str(step.reason_code or ''):<16} {str(step.funded):<7} "
            f"{step.weight:>6} {step.delta_pct:>7} {step.offset_before:>8} -> {step.offset_after:<8}"
        )
    print(f"\nOffset after {len(trace)} choices: {offset:+.2f} percentage points")


# --- Part 2 ----------------------------------------------------------------

CONSERVATIVE_ANSWERS = {
    "horizon": "lt_1y", "drawdown_reaction": "sell_all", "experience": "none", "goal": "preserve",
    "windfall_allocation": "fd_or_savings", "sure_gain_tradeoff": "guaranteed_5000", "friend_description": "real_risk_avoider",
}
AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y", "drawdown_reaction": "buy_a_lot", "experience": "extensive", "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow", "sure_gain_tradeoff": "chance_10pct_50000", "friend_description": "real_gambler",
}


def _mix_with_equity(displayed: dict[AssetClass, Decimal], equity: Decimal) -> dict[str, str]:
    """What the app's equity stepper sends: the other four classes rescaled
    in proportion so the mix still adds up to 100."""
    others = [ac for ac in AssetClass if ac != AssetClass.EQUITY]
    others_total = sum(displayed[ac] for ac in others)
    mix = {ac.value: (displayed[ac] * (100 - equity) / others_total).quantize(Decimal("0.01")) for ac in others}
    mix[AssetClass.EQUITY.value] = equity
    largest = max(others, key=lambda ac: mix[ac.value])
    mix[largest.value] += Decimal("100") - sum(mix.values())
    return {k: str(v) for k, v in mix.items()}


def _show(label: str, report) -> None:
    p, cap = report.personalized, report.personalized.cap
    base = report.target.target_pct[AssetClass.EQUITY]
    shown = p.displayed_target_pct[AssetClass.EQUITY]
    capped = f"  (asked for {cap.requested_offset_pct_points:+}, capped by {', '.join(constraint_label(c) for c in p.capacity_binding_constraints) or cap.cap_reason})" if cap.capped else ""
    print(
        f"  {label:<44} event {report.event.event_id[:8]}  tier {report.target.final_tier}  "
        f"equity {base}% -> shown {shown}%  offset {cap.applied_offset_pct_points:+}{capped}"
    )


def _respond(session: Session, user_id: str, report, label: str, **outcome) -> None:
    record_allocation_outcome(session, user_id, report.event.event_id, **outcome)
    print(f"    you: {label}")


def part_2() -> None:
    print("\n" + "=" * 78)
    print("PART 2 -- one live session through the real services (throwaway database)")
    print("=" * 78)
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = "demo-room-to-grow"
        upsert_profile(session, user_id=user, income_paise=100_000_00, income_stability=IncomeStability.REGULAR,
                       employment_type=EmploymentType.SALARIED, cash_balance_paise=10_000_000_00)
        add_holding(session, user_id=user, description="Equity fund", value_paise=5_00_000_00, holding_type=HoldingType.EQUITY_MUTUAL_FUND)
        compute_and_log_risk_tier(session, user, CONSERVATIVE_ANSWERS)
        print("\nA cautious user (tier 1) with strong finances (capacity ceiling 5): room to grow.\n")

        r = compute_and_log_allocation(session, user)
        _show("1. first plan", r)
        _respond(session, user, r, "set my own mix at 25% equity, and invested it",
                 action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix_with_equity(r.personalized.displayed_target_pct, Decimal("25")), funded=True)

        r = compute_and_log_allocation(session, user)
        _show("2. next plan learns from that", r)
        first_unfunded = r
        _respond(session, user, r, "set 28% equity, haven't invested yet (half weight)",
                 action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix_with_equity(r.personalized.displayed_target_pct, Decimal("28")), funded=False)

        r = compute_and_log_allocation(session, user)
        _show("3. next plan", r)
        _respond(session, user, r, "turned it down -- didn't understand it (no weight)",
                 action_taken=EditActionTaken.REJECTED, chosen_target_pct=None, funded=None, reason_code="dont_understand")

        r = compute_and_log_allocation(session, user)
        _show("4. unchanged: confusion taught nothing", r)
        mark_allocation_funded(session, user, first_unfunded.event.event_id)
        print("    you: \"I've invested it\" on choice 2 -- its weight goes 0.5 -> 1.0")

        r = compute_and_log_allocation(session, user)
        _show("5. after the follow-up", r)
        _respond(session, user, r, "kept the plan as shown (confirms the offset)",
                 action_taken=EditActionTaken.ACCEPTED, chosen_target_pct=None, funded=False)

        r = compute_and_log_allocation(session, user)
        _show("6. an accept holds the offset steady", r)

        reopened = compute_and_log_allocation(session, user)
        print(f"\n  Re-opening the screen reuses event {reopened.event.event_id[:8]}: "
              f"{'same suggestion, no duplicate row' if reopened.event.event_id == r.event.event_id else 'NEW ROW (unexpected)'}")

        compute_and_log_personalization(session, user)
        trace = get_trace(session, user, "personalization")
        print(f"\n  What the Transparency screen says: \"{trace.headline}\"")
        for fact in next(s for s in trace.sections if s.key == "step_by_step_trace").facts:
            print(f"    {fact.label}: {fact.value}")
            print(f"      {fact.note}")

        print("\nAn eager user (stated tier 5) with only 1.5 months of emergency buffer: capped at tier 2.\n")
        user = "demo-capped"
        upsert_profile(session, user_id=user, income_paise=100_000_00, income_stability=IncomeStability.REGULAR,
                       employment_type=EmploymentType.SALARIED, cash_balance_paise=30_000_00)
        add_expense_item(session, user_id=user, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
        add_holding(session, user_id=user, description="Equity fund", value_paise=1_00_000_00, holding_type=HoldingType.EQUITY_MUTUAL_FUND)
        compute_and_log_risk_tier(session, user, AGGRESSIVE_ANSWERS)

        r = compute_and_log_allocation(session, user)
        _show("1. first plan", r)
        _respond(session, user, r, "set 45% equity, and invested it",
                 action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix_with_equity(r.personalized.displayed_target_pct, Decimal("45")), funded=True)
        r = compute_and_log_allocation(session, user)
        _show("2. the cap holds -- and says so", r)

        trace = get_trace(session, user, "allocation", event_id=r.event.event_id)
        section = next(s for s in trace.sections if s.key == "personal_adjustment")
        cap_fact = next(f for f in section.facts if f.label == "Limit reached")
        print(f"\n  What the Transparency screen says: \"{cap_fact.value}\"")
        print(f"  ({cap_fact.note})")
    engine.dispose()


def main() -> None:
    # the trace text uses arrows; Windows consoles default to cp1252
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    part_1()
    part_2()


if __name__ == "__main__":
    main()
