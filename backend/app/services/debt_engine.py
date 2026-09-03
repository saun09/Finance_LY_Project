"""Module 6, debt half: pure, deterministic debt calculators. No I/O.

Every calculator here builds on debt_amortization.simulate_single_debt.
Avalanche/snowball additionally model the standard "waterfall" behavior:
once a debt is cleared, its own monthly payment is redirected as extra
payment toward the current target debt, on top of any extra payment the
user is already applying.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.services.debt_amortization import AmortizationResult, simulate_single_debt
from app.services.debt_leak_config import MAX_AMORTIZATION_MONTHS


@dataclass(frozen=True)
class DebtInput:
    debt_id: str
    outstanding_principal_paise: int
    monthly_payment_paise: int
    annual_rate_bps: int


def _monthly_rate(annual_rate_bps: int) -> Decimal:
    return Decimal(annual_rate_bps) / Decimal(10_000) / Decimal(12)


# --- avalanche vs snowball ---


@dataclass(frozen=True)
class StrategyResult:
    strategy: str  # "avalanche" | "snowball"
    months_to_clear_all: int
    total_interest_paise: int
    payoff_order: tuple[str, ...]  # debt_ids, in the order they were cleared
    converged: bool


@dataclass(frozen=True)
class AvalancheSnowballComparison:
    avalanche: StrategyResult
    snowball: StrategyResult
    interest_saved_by_avalanche_paise: int  # snowball interest - avalanche interest; can be 0 or negative
    months_saved_by_avalanche: int


def _simulate_waterfall(debts: list[DebtInput], extra_monthly_paise: int, order_key, strategy_name: str) -> StrategyResult:
    balances = {d.debt_id: Decimal(d.outstanding_principal_paise) for d in debts}
    rates = {d.debt_id: _monthly_rate(d.annual_rate_bps) for d in debts}
    payments = {d.debt_id: Decimal(d.monthly_payment_paise) for d in debts}

    remaining_order = sorted((d for d in debts if d.outstanding_principal_paise > 0), key=order_key)
    remaining_ids = [d.debt_id for d in remaining_order]

    total_interest = Decimal(0)
    payoff_order: list[str] = []
    months = 0
    freed_up_paise = Decimal(0)  # EMIs of already-cleared debts, redirected to the target

    while remaining_ids and months < MAX_AMORTIZATION_MONTHS:
        months += 1
        target_id = remaining_ids[0]

        for debt_id in list(remaining_ids):
            rate = rates[debt_id]
            balance = balances[debt_id]
            interest = (balance * rate).quantize(Decimal("1"))

            base_payment = payments[debt_id]
            if debt_id == target_id:
                base_payment += Decimal(extra_monthly_paise) + freed_up_paise

            this_payment = min(base_payment, balance + interest)
            principal_portion = this_payment - interest

            if principal_portion <= 0 and debt_id == target_id:
                # even the target debt's own payment can't cover its interest
                return StrategyResult(
                    strategy=strategy_name, months_to_clear_all=months, total_interest_paise=int(total_interest),
                    payoff_order=tuple(payoff_order), converged=False,
                )
            # a non-target debt whose own payment doesn't cover its interest
            # is held flat (not paid down further, but also not modeled as
            # negatively amortizing/growing) -- a simplification that only
            # matters for inconsistent input, since a real loan's EMI is
            # always calibrated to exceed its own interest.

            total_interest += interest
            balances[debt_id] = balance - max(principal_portion, Decimal(0))

            if balances[debt_id] <= 0:
                balances[debt_id] = Decimal(0)
                if debt_id in remaining_ids:
                    remaining_ids.remove(debt_id)
                    payoff_order.append(debt_id)
                    freed_up_paise += payments[debt_id]

    return StrategyResult(
        strategy=strategy_name, months_to_clear_all=months, total_interest_paise=int(total_interest.quantize(Decimal("1"))),
        payoff_order=tuple(payoff_order), converged=not remaining_ids,
    )


def compare_avalanche_vs_snowball(debts: list[DebtInput], extra_monthly_paise: int) -> AvalancheSnowballComparison:
    avalanche = _simulate_waterfall(debts, extra_monthly_paise, order_key=lambda d: -d.annual_rate_bps, strategy_name="avalanche")
    snowball = _simulate_waterfall(debts, extra_monthly_paise, order_key=lambda d: d.outstanding_principal_paise, strategy_name="snowball")

    return AvalancheSnowballComparison(
        avalanche=avalanche,
        snowball=snowball,
        interest_saved_by_avalanche_paise=snowball.total_interest_paise - avalanche.total_interest_paise,
        months_saved_by_avalanche=snowball.months_to_clear_all - avalanche.months_to_clear_all,
    )


# --- prepay vs invest ---


@dataclass(frozen=True)
class PrepayVsInvestResult:
    debt_id: str
    guaranteed_annual_rate_pct: Decimal
    extra_monthly_paise: int
    baseline_months: int
    baseline_total_interest_paise: int
    accelerated_months: int
    accelerated_total_interest_paise: int
    interest_saved_paise: int
    months_saved: int
    framing_note: str


def prepay_vs_invest_analysis(debt: DebtInput, extra_monthly_paise: int) -> PrepayVsInvestResult:
    baseline = simulate_single_debt(debt.outstanding_principal_paise, debt.annual_rate_bps, debt.monthly_payment_paise)
    accelerated = simulate_single_debt(
        debt.outstanding_principal_paise, debt.annual_rate_bps, debt.monthly_payment_paise + extra_monthly_paise
    )

    rate_pct = (Decimal(debt.annual_rate_bps) / 100).quantize(Decimal("0.01"))

    framing_note = (
        f"Prepaying this debt guarantees a return equal to its interest rate ({rate_pct}% p.a.): "
        "every extra rupee that goes toward principal stops accruing that interest, with no market "
        "risk and no dependence on timing. Investing the same amount instead only comes out ahead if "
        f"it earns more than {rate_pct}% per year after tax and fees, which is never guaranteed. This "
        "app does not project what an investment would return, because it can't promise what markets "
        "will do -- only your own debt's rate is certain."
    )

    return PrepayVsInvestResult(
        debt_id=debt.debt_id,
        guaranteed_annual_rate_pct=rate_pct,
        extra_monthly_paise=extra_monthly_paise,
        baseline_months=baseline.months,
        baseline_total_interest_paise=baseline.total_interest_paise,
        accelerated_months=accelerated.months,
        accelerated_total_interest_paise=accelerated.total_interest_paise,
        interest_saved_paise=baseline.total_interest_paise - accelerated.total_interest_paise,
        months_saved=baseline.months - accelerated.months,
        framing_note=framing_note,
    )


# --- credit card revolving cost ---


@dataclass(frozen=True)
class CreditCardRevolvingCostResult:
    nominal_annual_rate_pct: Decimal  # naive monthly_rate * 12
    effective_annual_rate_pct: Decimal  # (1 + monthly_rate)^12 - 1, i.e. the real compounded cost
    months_to_clear_at_minimum: int
    total_interest_at_minimum_paise: int
    converged: bool


def credit_card_revolving_cost(
    balance_paise: int,
    monthly_rate_bps: int,
    min_payment_pct_bps: int,
    min_payment_floor_paise: int,
) -> CreditCardRevolvingCostResult:
    monthly_rate = Decimal(monthly_rate_bps) / Decimal(10_000)
    nominal_annual = (monthly_rate * 12 * 100).quantize(Decimal("0.01"))
    effective_annual = (((1 + monthly_rate) ** 12 - 1) * 100).quantize(Decimal("0.01"))

    balance = Decimal(balance_paise)
    min_pct = Decimal(min_payment_pct_bps) / Decimal(10_000)
    floor = Decimal(min_payment_floor_paise)

    total_interest = Decimal(0)
    months = 0

    while balance > 0 and months < MAX_AMORTIZATION_MONTHS:
        interest = (balance * monthly_rate).quantize(Decimal("1"))
        min_payment = max((balance * min_pct).quantize(Decimal("1"), rounding=ROUND_HALF_UP), floor)
        this_payment = min(min_payment, balance + interest)
        principal_portion = this_payment - interest

        if principal_portion <= 0:
            return CreditCardRevolvingCostResult(
                nominal_annual_rate_pct=nominal_annual, effective_annual_rate_pct=effective_annual,
                months_to_clear_at_minimum=months, total_interest_at_minimum_paise=int(total_interest),
                converged=False,
            )

        total_interest += interest
        balance -= principal_portion
        months += 1

    return CreditCardRevolvingCostResult(
        nominal_annual_rate_pct=nominal_annual,
        effective_annual_rate_pct=effective_annual,
        months_to_clear_at_minimum=months,
        total_interest_at_minimum_paise=int(total_interest.quantize(Decimal("1"))),
        converged=balance <= 0,
    )


# --- refinance breakeven ---


@dataclass(frozen=True)
class RefinanceBreakevenResult:
    current_monthly_payment_paise: int
    new_monthly_payment_paise: int
    monthly_savings_paise: int
    fees_paise: int
    breakeven_month: int | None  # None if refinancing never recovers its fees
    beneficial: bool


def _emi_for(principal_paise: int, annual_rate_bps: int, tenure_months: int) -> int:
    if tenure_months <= 0:
        return 0
    monthly_rate = _monthly_rate(annual_rate_bps)
    principal = Decimal(principal_paise)
    if monthly_rate == 0:
        emi = principal / tenure_months
    else:
        emi = principal * monthly_rate * (1 + monthly_rate) ** tenure_months / ((1 + monthly_rate) ** tenure_months - 1)
    return int(emi.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def refinance_breakeven(
    outstanding_principal_paise: int,
    remaining_tenure_months: int,
    current_monthly_payment_paise: int,
    new_annual_rate_bps: int,
    fees_paise: int,
) -> RefinanceBreakevenResult:
    new_payment = _emi_for(outstanding_principal_paise, new_annual_rate_bps, remaining_tenure_months)
    monthly_savings = current_monthly_payment_paise - new_payment

    if monthly_savings <= 0:
        return RefinanceBreakevenResult(
            current_monthly_payment_paise=current_monthly_payment_paise, new_monthly_payment_paise=new_payment,
            monthly_savings_paise=monthly_savings, fees_paise=fees_paise, breakeven_month=None, beneficial=False,
        )

    breakeven_month = math.ceil(fees_paise / monthly_savings) if fees_paise > 0 else 0
    beneficial = breakeven_month <= remaining_tenure_months

    return RefinanceBreakevenResult(
        current_monthly_payment_paise=current_monthly_payment_paise,
        new_monthly_payment_paise=new_payment,
        monthly_savings_paise=monthly_savings,
        fees_paise=fees_paise,
        breakeven_month=breakeven_month,
        beneficial=beneficial,
    )
