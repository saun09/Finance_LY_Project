"""Shared amortization simulation primitives for Module 6. Pure, no I/O —
every debt calculator in debt_engine.py builds on `simulate_single_debt`.

All simulations work in integer paise and whole months. Interest accrues
monthly at the loan's own monthly rate (annual_rate_bps / 10000 / 12);
each month's payment first covers accrued interest, with the remainder
reducing principal. This is standard amortization, not a simplification —
it's the same math as financial_position.compute_outstanding_principal,
just run forward instead of solved in closed form (a closed-form PV
formula can't model a *changing* monthly payment, which avalanche/snowball
strategies require once a debt is paid off and its EMI gets redirected).
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.debt_leak_config import MAX_AMORTIZATION_MONTHS


@dataclass(frozen=True)
class AmortizationResult:
    months: int
    total_interest_paise: int
    converged: bool  # False if MAX_AMORTIZATION_MONTHS was hit without payoff


def _monthly_rate(annual_rate_bps: int) -> Decimal:
    return Decimal(annual_rate_bps) / Decimal(10_000) / Decimal(12)


def simulate_single_debt(
    principal_paise: int,
    annual_rate_bps: int,
    monthly_payment_paise: int,
    max_months: int = MAX_AMORTIZATION_MONTHS,
) -> AmortizationResult:
    """Pay a single debt down at a fixed monthly payment until it clears."""
    if principal_paise <= 0:
        return AmortizationResult(months=0, total_interest_paise=0, converged=True)

    rate = _monthly_rate(annual_rate_bps)
    balance = Decimal(principal_paise)
    payment = Decimal(monthly_payment_paise)
    total_interest = Decimal(0)
    months = 0

    while balance > 0 and months < max_months:
        interest = (balance * rate).quantize(Decimal("1"))
        this_payment = min(payment, balance + interest)  # never overpay past payoff
        principal_portion = this_payment - interest

        if principal_portion <= 0:
            # payment doesn't even cover accruing interest -- balance would
            # grow forever; stop and report non-convergence rather than loop
            return AmortizationResult(months=months, total_interest_paise=int(total_interest), converged=False)

        total_interest += interest
        balance -= principal_portion
        months += 1

    return AmortizationResult(
        months=months,
        total_interest_paise=int(total_interest.quantize(Decimal("1"))),
        converged=balance <= 0,
    )
