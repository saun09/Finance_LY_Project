from decimal import Decimal

from app.services.debt_engine import (
    DebtInput,
    compare_avalanche_vs_snowball,
    credit_card_revolving_cost,
    prepay_vs_invest_analysis,
    refinance_breakeven,
)

# --- avalanche vs snowball ---


def test_single_debt_avalanche_and_snowball_are_identical():
    debt = [DebtInput("only", 200_000_00, 8_000_00, 1000)]
    result = compare_avalanche_vs_snowball(debt, 5_000_00)
    assert result.avalanche.months_to_clear_all == result.snowball.months_to_clear_all
    assert result.avalanche.total_interest_paise == result.snowball.total_interest_paise
    assert result.interest_saved_by_avalanche_paise == 0


def test_avalanche_saves_at_least_as_much_interest_as_snowball_hand_checked():
    # a large, high-rate debt and a small, low-rate debt -- the classic
    # case where avalanche (rate-first) and snowball (balance-first) give
    # genuinely different extra-payment targets
    debts = [
        DebtInput("A_high_rate", 500_000_00, 15_000_00, 1800),  # Rs 5,00,000 @ 18% p.a.
        DebtInput("B_low_rate", 100_000_00, 5_000_00, 800),  # Rs 1,00,000 @ 8% p.a.
    ]
    result = compare_avalanche_vs_snowball(debts, 10_000_00)

    assert result.avalanche.converged is True
    assert result.snowball.converged is True
    assert result.avalanche.total_interest_paise == 10_652_552
    assert result.snowball.total_interest_paise == 11_486_583
    assert result.interest_saved_by_avalanche_paise == 834_031
    assert result.interest_saved_by_avalanche_paise > 0  # avalanche never costs more, in general
    assert set(result.avalanche.payoff_order) == {"A_high_rate", "B_low_rate"}


def test_avalanche_never_costs_more_interest_than_snowball_property_check():
    # a broader, differently-parameterized scenario, checked only for the
    # general mathematical property (avalanche is interest-optimal among
    # fixed-order waterfall strategies), not exact figures
    debts = [
        DebtInput("card", 150_000_00, 6_000_00, 3600),
        DebtInput("personal_loan", 300_000_00, 9_000_00, 1400),
        DebtInput("car_loan", 400_000_00, 10_000_00, 900),
    ]
    result = compare_avalanche_vs_snowball(debts, 8_000_00)
    assert result.avalanche.converged and result.snowball.converged
    assert result.interest_saved_by_avalanche_paise >= 0


def test_debt_that_cannot_be_serviced_reports_non_convergence():
    debts = [DebtInput("underwater", 1_000_000_00, 1_000_00, 3600)]  # tiny payment vs 36% p.a.
    result = compare_avalanche_vs_snowball(debts, 0)
    assert result.avalanche.converged is False


# --- prepay vs invest ---


def test_prepay_vs_invest_hand_checked():
    debt = DebtInput("loan1", 112_551, 10_000, 1200)
    result = prepay_vs_invest_analysis(debt, extra_monthly_paise=5_000)

    assert result.guaranteed_annual_rate_pct == Decimal("12.00")
    assert result.baseline_months == 13
    assert result.baseline_total_interest_paise == 7_450
    assert result.accelerated_months == 8
    assert result.accelerated_total_interest_paise == 5_042
    assert result.interest_saved_paise == 2_408
    assert result.months_saved == 5


def test_prepay_vs_invest_framing_is_explicit_about_certain_vs_speculative():
    debt = DebtInput("loan1", 112_551, 10_000, 1200)
    result = prepay_vs_invest_analysis(debt, extra_monthly_paise=5_000)

    assert "guarantees" in result.framing_note
    assert "12.00%" in result.framing_note
    assert "not guaranteed" in result.framing_note or "never guaranteed" in result.framing_note
    # the note must not itself assert what an investment would return
    assert "app does not project" in result.framing_note


# --- credit card revolving cost ---


def test_credit_card_effective_rate_exceeds_nominal_due_to_compounding():
    result = credit_card_revolving_cost(
        balance_paise=50_000_00, monthly_rate_bps=350, min_payment_pct_bps=500, min_payment_floor_paise=50_00
    )
    assert result.nominal_annual_rate_pct == Decimal("42.00")
    assert result.effective_annual_rate_pct == Decimal("51.11")
    assert result.effective_annual_rate_pct > result.nominal_annual_rate_pct
    assert result.converged is True
    assert result.months_to_clear_at_minimum == 294
    assert result.total_interest_at_minimum_paise == 11_508_325


def test_credit_card_minimum_payment_trap_takes_a_very_long_time():
    # percentage-of-balance minimum payments are the classic "minimum
    # payment trap": payoff should take many years, not months
    result = credit_card_revolving_cost(
        balance_paise=50_000_00, monthly_rate_bps=350, min_payment_pct_bps=500, min_payment_floor_paise=50_00
    )
    assert result.months_to_clear_at_minimum > 120  # more than 10 years


# --- refinance breakeven ---


def test_refinance_breakeven_hand_checked():
    result = refinance_breakeven(
        outstanding_principal_paise=500_000_00,
        remaining_tenure_months=120,
        current_monthly_payment_paise=6_500_00,
        new_annual_rate_bps=850,
        fees_paise=15_000_00,
    )
    assert result.new_monthly_payment_paise == 619_928
    assert result.monthly_savings_paise == 30_072
    assert result.breakeven_month == 50
    assert result.beneficial is True


def test_refinance_not_beneficial_when_new_rate_is_worse():
    result = refinance_breakeven(
        outstanding_principal_paise=500_000_00,
        remaining_tenure_months=120,
        current_monthly_payment_paise=6_500_00,
        new_annual_rate_bps=1400,  # a high rate that produces a worse EMI than the current payment
        fees_paise=15_000_00,
    )
    assert result.monthly_savings_paise <= 0
    assert result.breakeven_month is None
    assert result.beneficial is False


def test_refinance_not_beneficial_when_breakeven_exceeds_remaining_tenure():
    result = refinance_breakeven(
        outstanding_principal_paise=500_000_00,
        remaining_tenure_months=6,  # loan almost over
        current_monthly_payment_paise=6_500_00,
        new_annual_rate_bps=850,
        fees_paise=15_000_00,  # large fee relative to tiny remaining term
    )
    assert result.beneficial is False


def test_refinance_zero_fees_breaks_even_immediately():
    result = refinance_breakeven(
        outstanding_principal_paise=500_000_00,
        remaining_tenure_months=120,
        current_monthly_payment_paise=6_500_00,
        new_annual_rate_bps=850,
        fees_paise=0,
    )
    assert result.breakeven_month == 0
    assert result.beneficial is True
