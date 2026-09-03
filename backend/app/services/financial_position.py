"""Pure, deterministic financial-position calculations for Module 2.

No I/O, no ORM, no model calls — these take plain values/dataclasses and
return numbers, so they're independently unit-testable against hand-checked
cases per the project's convention that scoring/money math must be pure.

All money in and out is integer paise. `debt_to_income_ratio` and
`buffer_coverage_months` are ratios, stored as Decimal to match Module 1's
NUMERIC(6,4)/NUMERIC(6,2) snapshot columns, which are NOT NULL — so the
zero-denominator edge cases below resolve to a well-defined Decimal rather
than None, using the documented sentinel caps at the bottom of this file
instead of leaving the snapshot un-writable.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum


class ExpenseFrequency(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"
    ONE_TIME = "one_time"


@dataclass(frozen=True)
class EmiInput:
    amount_paise: int  # the monthly EMI payment itself
    remaining_tenure_months: int
    annual_rate_bps: int  # e.g. 950 = 9.50% p.a.


@dataclass(frozen=True)
class ExpenseInput:
    amount_paise: int
    frequency: ExpenseFrequency
    is_essential: bool


# NUMERIC(6,2) on user_monthly_snapshot.buffer_coverage_months maxes out at
# 9999.99; NUMERIC(6,4) on debt_to_income_ratio maxes out at 9.9999. Both
# ratios are capped at these ceilings rather than left undefined so a
# snapshot can always be written — see compute_emergency_fund_coverage_months
# and compute_emi_to_income_ratio for when the cap is actually hit.
MAX_BUFFER_MONTHS = Decimal("9999.99")
MAX_EMI_TO_INCOME_RATIO = Decimal("9.9999")


def _monthly_equivalent_paise(item: ExpenseInput) -> int:
    """Normalize one expense line item to its monthly run-rate. One-time
    items contribute 0 — they're real spends but not a recurring monthly
    obligation, so including them would distort surplus/buffer going
    forward."""
    if item.frequency == ExpenseFrequency.MONTHLY:
        return item.amount_paise
    if item.frequency == ExpenseFrequency.ANNUAL:
        monthly = Decimal(item.amount_paise) / Decimal(12)
        return int(monthly.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return 0  # ONE_TIME


def compute_total_monthly_expenses(expenses: list[ExpenseInput]) -> int:
    """All recorded expenses (essential + discretionary), normalized to a
    monthly figure. This is the "expenses" term in monthly surplus."""
    return sum(_monthly_equivalent_paise(e) for e in expenses)


def compute_average_monthly_essential_expense(expenses: list[ExpenseInput]) -> int:
    """Only the essential subset, normalized to monthly. This is the
    denominator of emergency-fund coverage — discretionary spending isn't
    what a buffer needs to cover."""
    return sum(_monthly_equivalent_paise(e) for e in expenses if e.is_essential)


def compute_total_monthly_emi(emis: list[EmiInput]) -> int:
    return sum(e.amount_paise for e in emis)


def compute_outstanding_principal(emi: EmiInput) -> int:
    """Present value of the remaining EMI payments at the loan's own rate,
    rounded to the nearest paise. Onboarding captures the payment schedule
    (amount/tenure/rate), not a separately-tracked outstanding balance, so
    this is how a loan's current liability is derived for net worth."""
    if emi.remaining_tenure_months <= 0 or emi.amount_paise <= 0:
        return 0

    monthly_rate = Decimal(emi.annual_rate_bps) / Decimal(10_000) / Decimal(12)
    payment = Decimal(emi.amount_paise)
    n = emi.remaining_tenure_months

    if monthly_rate == 0:
        present_value = payment * n
    else:
        present_value = payment * (1 - (1 + monthly_rate) ** (-n)) / monthly_rate

    return int(present_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_net_worth(cash_balance_paise: int, holdings_paise: list[int], emis: list[EmiInput]) -> int:
    assets = cash_balance_paise + sum(holdings_paise)
    liabilities = sum(compute_outstanding_principal(e) for e in emis)
    return assets - liabilities


def compute_monthly_surplus(income_paise: int, total_monthly_expenses_paise: int, total_monthly_emi_paise: int) -> int:
    return income_paise - total_monthly_expenses_paise - total_monthly_emi_paise


def compute_emergency_fund_coverage_months(
    liquid_cash_paise: int, avg_monthly_essential_expense_paise: int
) -> Decimal:
    """liquid cash+equivalents / average monthly essential expense.

    "Liquid cash+equivalents" here means exactly the user's declared cash
    balance, not the freeform holdings list — holdings aren't classified by
    liquidity yet (that's a later module), so including them would risk
    counting illiquid assets toward an emergency buffer.

    If there's no essential-expense baseline yet: zero cash against zero
    essential expense is trivially zero months of buffer; any positive cash
    against zero essential expense is capped at MAX_BUFFER_MONTHS rather
    than treated as literally infinite, since the snapshot column can't
    store null or infinity. Callers should treat a value at the cap as "not
    meaningfully measurable yet," not a literal figure.
    """
    if avg_monthly_essential_expense_paise <= 0:
        return Decimal("0.00") if liquid_cash_paise <= 0 else MAX_BUFFER_MONTHS

    ratio = Decimal(liquid_cash_paise) / Decimal(avg_monthly_essential_expense_paise)
    return min(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), MAX_BUFFER_MONTHS)


def compute_emi_to_income_ratio(total_monthly_emi_paise: int, income_paise: int) -> Decimal:
    """total EMI payments / income.

    Zero income with zero EMI is trivially a zero ratio. Zero income with
    any EMI at all is capped at MAX_EMI_TO_INCOME_RATIO rather than treated
    as literally undefined — which is the semantically right call here, not
    just a technical workaround: a user with no income and existing debt
    genuinely has an extreme, ability-capping burden, and the cap conveys
    "severe" rather than crashing or silently reporting zero burden.
    """
    if income_paise <= 0:
        return Decimal("0.0000") if total_monthly_emi_paise <= 0 else MAX_EMI_TO_INCOME_RATIO

    ratio = Decimal(total_monthly_emi_paise) / Decimal(income_paise)
    return min(ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), MAX_EMI_TO_INCOME_RATIO)
