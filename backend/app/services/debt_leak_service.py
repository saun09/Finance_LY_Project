"""Wires Module 6's pure debt/leak logic to Module 2's EMIs, expenses,
profile, and expense-source decision, and to Module 1's event log. This is
the only layer in Module 6 that touches the database.

The main entry point, `compute_and_log_debt_leak_report`, produces the
single combined "headline recoverable Rs/year" output the module brief
asks for. That headline is built ONLY from the leak side (idle cash, fee
drag, flagged recurring charges) because those are genuinely ongoing
annual amounts fully derivable from stored data with no extra input.
Avalanche/snowball and prepay-vs-invest are reported alongside as their
own outputs, not folded into the annual headline: their savings are a
one-time/multi-year total over a payoff horizon, not a perpetual yearly
figure, and forcing them into a "per year" number would misrepresent them.
Refinance-breakeven and the credit-card revolving-cost calculator are
separate, input-driven tools (they need a hypothetical new rate, or a
revolving balance Module 2 doesn't model as an EMI) and are exposed as
standalone pure-function wrappers, not part of the automatic report.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import EmiEntry, ExpenseItem
from app.services.debt_engine import (
    AvalancheSnowballComparison,
    DebtInput,
    PrepayVsInvestResult,
    RefinanceBreakevenResult,
    compare_avalanche_vs_snowball,
    prepay_vs_invest_analysis,
    refinance_breakeven,
)
from app.services.event_log import log_suggestion_event
from app.services.financial_position import EmiInput, compute_outstanding_principal
from app.services.leak_engine import ExpenseItemInput, LeakReport, build_leak_report
from app.services.onboarding import ProfileNotFoundError, compute_financial_position, get_expense_source_mode, get_profile


class EmiNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class DebtLeakReport:
    avalanche_snowball: AvalancheSnowballComparison | None
    prepay_vs_invest: PrepayVsInvestResult | None
    leak: LeakReport
    total_recoverable_annual_paise: int
    expense_source_mode: str
    expense_source_is_explicit: bool


def _gather_debts(session: Session, user_id: str) -> list[DebtInput]:
    rows = session.execute(
        select(EmiEntry).where(EmiEntry.user_id == user_id, EmiEntry.closed_at.is_(None))
    ).scalars().all()
    return [
        DebtInput(
            debt_id=e.id,
            outstanding_principal_paise=compute_outstanding_principal(
                EmiInput(amount_paise=e.amount_paise, remaining_tenure_months=e.remaining_tenure_months, annual_rate_bps=e.annual_rate_bps)
            ),
            monthly_payment_paise=e.amount_paise,
            annual_rate_bps=e.annual_rate_bps,
        )
        for e in rows
    ]


def _gather_expense_items(session: Session, user_id: str) -> list[ExpenseItemInput]:
    rows = session.execute(
        select(ExpenseItem).where(ExpenseItem.user_id == user_id, ExpenseItem.removed_at.is_(None))
    ).scalars().all()
    return [
        ExpenseItemInput(item_id=e.id, category=e.category, amount_paise=e.amount_paise, frequency=e.frequency, is_essential=e.is_essential)
        for e in rows
    ]


def compute_and_log_debt_leak_report(session: Session, user_id: str, commit: bool = True) -> DebtLeakReport:
    profile = get_profile(session, user_id)
    if profile is None:
        raise ProfileNotFoundError(f"no user_profile for user_id={user_id!r}; complete Module 2 onboarding first")

    debts = _gather_debts(session, user_id)
    expense_items = _gather_expense_items(session, user_id)
    position = compute_financial_position(session, user_id)
    resolved_mode = get_expense_source_mode(session, user_id)

    surplus_paise = max(0, position["monthly_surplus_paise"])

    avalanche_snowball = None
    prepay_vs_invest = None
    if debts and surplus_paise > 0:
        avalanche_snowball = compare_avalanche_vs_snowball(debts, surplus_paise)
        top_rate_debt = max(debts, key=lambda d: d.annual_rate_bps)
        prepay_vs_invest = prepay_vs_invest_analysis(top_rate_debt, surplus_paise)

    leak = build_leak_report(profile.cash_balance_paise, position["essential_monthly_expense_paise"], expense_items)

    log_suggestion_event(
        session,
        user_id=user_id,
        module_source="debt_leak_engine",
        suggested_value={
            "total_recoverable_annual_paise": leak.total_recoverable_annual_paise,
            "leak_components": [
                {
                    "component_id": c.component_id,
                    "label": c.label,
                    "annual_amount_paise": c.annual_amount_paise,
                    "explanation": c.explanation,
                    "concrete_action": c.concrete_action,
                }
                for c in leak.components
            ],
            "idle_cash": {
                "required_buffer_paise": leak.idle_cash.required_buffer_paise,
                "idle_cash_paise": leak.idle_cash.idle_cash_paise,
                "reference_rate_annual_pct": str(leak.idle_cash.reference_rate_annual_pct),
                "opportunity_cost_annual_paise": leak.idle_cash.opportunity_cost_annual_paise,
            },
            "fee_drag_total_annual_paise": leak.fee_drag.total_annual_paise,
            "recurring_candidate_count": len(leak.recurring_candidates),
            "data_source_note": leak.data_source_note,
            "avalanche_snowball": (
                None
                if avalanche_snowball is None
                else {
                    "avalanche_months": avalanche_snowball.avalanche.months_to_clear_all,
                    "avalanche_total_interest_paise": avalanche_snowball.avalanche.total_interest_paise,
                    "avalanche_converged": avalanche_snowball.avalanche.converged,
                    "snowball_months": avalanche_snowball.snowball.months_to_clear_all,
                    "snowball_total_interest_paise": avalanche_snowball.snowball.total_interest_paise,
                    "snowball_converged": avalanche_snowball.snowball.converged,
                    "interest_saved_by_avalanche_paise": avalanche_snowball.interest_saved_by_avalanche_paise,
                    "months_saved_by_avalanche": avalanche_snowball.months_saved_by_avalanche,
                }
            ),
            "prepay_vs_invest": (
                None
                if prepay_vs_invest is None
                else {
                    "debt_id": prepay_vs_invest.debt_id,
                    "guaranteed_annual_rate_pct": str(prepay_vs_invest.guaranteed_annual_rate_pct),
                    "extra_monthly_paise": prepay_vs_invest.extra_monthly_paise,
                    "interest_saved_paise": prepay_vs_invest.interest_saved_paise,
                    "months_saved": prepay_vs_invest.months_saved,
                    "framing_note": prepay_vs_invest.framing_note,
                }
            ),
        },
        market_context={
            "expense_source_mode": resolved_mode.mode.value,
            "expense_source_mode_is_explicit": resolved_mode.is_explicit_decision,
            "surplus_used_as_extra_payment_paise": surplus_paise,
            "debt_count": len(debts),
            "expense_item_count": len(expense_items),
        },
        commit=commit,
    )

    return DebtLeakReport(
        avalanche_snowball=avalanche_snowball,
        prepay_vs_invest=prepay_vs_invest,
        leak=leak,
        total_recoverable_annual_paise=leak.total_recoverable_annual_paise,
        expense_source_mode=resolved_mode.mode.value,
        expense_source_is_explicit=resolved_mode.is_explicit_decision,
    )


def compute_refinance_breakeven_for_emi(
    session: Session, user_id: str, emi_id: str, new_annual_rate_bps: int, fees_paise: int
) -> RefinanceBreakevenResult:
    """Refinance-breakeven for one of the user's existing EMIs, looked up
    by id -- an on-demand calculator, not part of the automatic report,
    since it needs a hypothetical new rate/fees this module has no way to
    know on its own."""
    emi = session.get(EmiEntry, emi_id)
    if emi is None or emi.user_id != user_id:
        raise EmiNotFoundError(f"no EMI with id={emi_id!r} for user_id={user_id!r}")

    outstanding_principal = compute_outstanding_principal(
        EmiInput(amount_paise=emi.amount_paise, remaining_tenure_months=emi.remaining_tenure_months, annual_rate_bps=emi.annual_rate_bps)
    )
    return refinance_breakeven(
        outstanding_principal_paise=outstanding_principal,
        remaining_tenure_months=emi.remaining_tenure_months,
        current_monthly_payment_paise=emi.amount_paise,
        new_annual_rate_bps=new_annual_rate_bps,
        fees_paise=fees_paise,
    )
