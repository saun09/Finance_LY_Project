from app.services.debt_amortization import simulate_single_debt


def test_zero_principal_converges_immediately():
    result = simulate_single_debt(0, 1000, 5000)
    assert result.months == 0
    assert result.total_interest_paise == 0
    assert result.converged is True


def test_zero_interest_loan_pays_exactly_principal_over_the_dollar_count_of_payments():
    # no interest: 120000 paise / 10000 paise per month = 12 months, zero interest
    result = simulate_single_debt(120_000, 0, 10_000)
    assert result.months == 12
    assert result.total_interest_paise == 0
    assert result.converged is True


def test_matches_the_closed_form_annuity_pv_within_a_rounding_month():
    # from financial_position's hand-checked case: EMI 10,000 paise/mo,
    # 12 months, 12% p.a. has PV == 112,551 paise. Simulating that exact
    # PV at that exact payment should clear in about 12 months (rounding
    # to whole paise each month can push this to 13 with a small final
    # payment -- that's a real amortization-schedule artifact, not a bug).
    result = simulate_single_debt(112_551, 1200, 10_000)
    assert result.months in (12, 13)
    assert result.converged is True
    # total interest should be close to 12*10,000 - 112,551 = 7,449 paise
    assert abs(result.total_interest_paise - 7_449) <= 5


def test_payment_below_accruing_interest_does_not_converge():
    # 100,000 paise at 24% p.a. accrues 2,000 paise/month interest;
    # a 1,000 paise payment can never even cover that
    result = simulate_single_debt(100_000, 2400, 1_000)
    assert result.converged is False


def test_higher_payment_clears_faster_and_costs_less_interest():
    slow = simulate_single_debt(500_000, 1200, 15_000)
    fast = simulate_single_debt(500_000, 1200, 30_000)
    assert fast.months < slow.months
    assert fast.total_interest_paise < slow.total_interest_paise
