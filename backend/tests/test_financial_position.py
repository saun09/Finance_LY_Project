from decimal import Decimal

from app.services.financial_position import (
    MAX_BUFFER_MONTHS,
    MAX_EMI_TO_INCOME_RATIO,
    EmiInput,
    ExpenseFrequency,
    ExpenseInput,
    compute_average_monthly_essential_expense,
    compute_emergency_fund_coverage_months,
    compute_emi_to_income_ratio,
    compute_monthly_surplus,
    compute_net_worth,
    compute_outstanding_principal,
    compute_total_monthly_emi,
    compute_total_monthly_expenses,
)


# --- compute_outstanding_principal: hand-checked against an independent
# reference implementation of the standard annuity-PV formula ---


def test_outstanding_principal_hand_checked_case_a():
    emi = EmiInput(amount_paise=10_000, remaining_tenure_months=12, annual_rate_bps=1200)
    assert compute_outstanding_principal(emi) == 112_551


def test_outstanding_principal_hand_checked_case_b():
    emi = EmiInput(amount_paise=500_000, remaining_tenure_months=24, annual_rate_bps=900)
    assert compute_outstanding_principal(emi) == 10_944_573


def test_outstanding_principal_zero_interest_is_undiscounted_sum():
    emi = EmiInput(amount_paise=200_000, remaining_tenure_months=6, annual_rate_bps=0)
    assert compute_outstanding_principal(emi) == 1_200_000


def test_outstanding_principal_zero_remaining_tenure_is_zero():
    emi = EmiInput(amount_paise=100_000, remaining_tenure_months=0, annual_rate_bps=1000)
    assert compute_outstanding_principal(emi) == 0


# --- expense normalization ---


def test_monthly_equivalent_normalizes_annual_and_drops_one_time():
    expenses = [
        ExpenseInput(amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True),  # rent
        ExpenseInput(amount_paise=24_000_00, frequency=ExpenseFrequency.ANNUAL, is_essential=True),  # insurance
        ExpenseInput(amount_paise=50_000_00, frequency=ExpenseFrequency.ONE_TIME, is_essential=False),  # laptop
    ]
    # rent 2,000,000 + insurance 24,000,00/12=200,000 = 2,200,000; one-time excluded
    assert compute_total_monthly_expenses(expenses) == 2_200_000
    assert compute_average_monthly_essential_expense(expenses) == 2_200_000  # both counted items are essential


def test_average_monthly_essential_expense_excludes_discretionary():
    expenses = [
        ExpenseInput(amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True),
        ExpenseInput(amount_paise=5_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=False),
    ]
    assert compute_total_monthly_expenses(expenses) == 25_000_00
    assert compute_average_monthly_essential_expense(expenses) == 20_000_00


# --- a full hand-checked scenario tying every metric together ---


def _scenario():
    income = 80_000_00
    cash = 200_000_00
    holdings = [150_000_00, 50_000_00]
    emi = EmiInput(amount_paise=25_000_00, remaining_tenure_months=240, annual_rate_bps=850)
    expenses = [
        ExpenseInput(amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True),  # rent
        ExpenseInput(amount_paise=8_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True),  # groceries
        ExpenseInput(amount_paise=5_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=False),  # dining out
        ExpenseInput(amount_paise=24_000_00, frequency=ExpenseFrequency.ANNUAL, is_essential=True),  # insurance
    ]
    return income, cash, holdings, emi, expenses


def test_scenario_net_worth():
    income, cash, holdings, emi, expenses = _scenario()
    assert compute_net_worth(cash, holdings, [emi]) == -248_077_100


def test_scenario_monthly_surplus():
    income, cash, holdings, emi, expenses = _scenario()
    total_expenses = compute_total_monthly_expenses(expenses)
    total_emi = compute_total_monthly_emi([emi])
    assert total_expenses == 35_000_00
    assert total_emi == 25_000_00
    assert compute_monthly_surplus(income, total_expenses, total_emi) == 20_000_00


def test_scenario_buffer_months():
    income, cash, holdings, emi, expenses = _scenario()
    essential = compute_average_monthly_essential_expense(expenses)
    assert essential == 30_000_00
    assert compute_emergency_fund_coverage_months(cash, essential) == Decimal("6.67")


def test_scenario_emi_to_income_ratio():
    income, cash, holdings, emi, expenses = _scenario()
    total_emi = compute_total_monthly_emi([emi])
    assert compute_emi_to_income_ratio(total_emi, income) == Decimal("0.3125")


# --- zero-denominator edge cases (snapshot columns are NOT NULL, so these
# must resolve to a defined Decimal, not None/exception) ---


def test_buffer_months_zero_cash_zero_essential_expense_is_zero():
    assert compute_emergency_fund_coverage_months(0, 0) == Decimal("0.00")


def test_buffer_months_positive_cash_zero_essential_expense_is_capped():
    assert compute_emergency_fund_coverage_months(500_000_00, 0) == MAX_BUFFER_MONTHS


def test_emi_ratio_zero_income_zero_emi_is_zero():
    assert compute_emi_to_income_ratio(0, 0) == Decimal("0.0000")


def test_emi_ratio_zero_income_with_emi_is_capped():
    assert compute_emi_to_income_ratio(10_000_00, 0) == MAX_EMI_TO_INCOME_RATIO


def test_net_worth_with_no_emis_or_holdings_is_just_cash():
    assert compute_net_worth(50_000_00, [], []) == 50_000_00
