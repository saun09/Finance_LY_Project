from decimal import Decimal

from app.services.risk_profile import (
    CapacityInputs,
    IncomeStabilityValue,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
}
CONSERVATIVE_ANSWERS = {
    "horizon": "lt_1y",
    "drawdown_reaction": "sell_all",
    "experience": "none",
    "goal": "preserve",
}


def test_uncapped_when_capacity_meets_or_exceeds_stated():
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)  # tier 5
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("6.00"),
        emi_to_income_ratio=Decimal("0.10"),
        income_stability=IncomeStabilityValue.REGULAR,
        dependents_count=0,
        total_life_cover_paise=0,
        monthly_income_paise=100_000_00,
        cash_balance_paise=600_000_00,
        essential_monthly_expense_paise=100_000_00,
        total_monthly_emi_paise=10_000_00,
    )
    capacity = compute_capacity_ceiling(inputs)
    result = compute_final_tier(stated, capacity, inputs)

    assert result.stated_tier == 5
    assert result.capacity_ceiling == 5
    assert result.final_tier == 5
    assert result.capped is False
    assert result.binding_constraints == ()
    assert result.unlock_conditions == ()


def test_conservative_answers_are_never_capped_even_with_poor_capacity():
    stated = compute_stated_tier(CONSERVATIVE_ANSWERS)  # tier 1
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("0.00"),
        emi_to_income_ratio=Decimal("0.90"),
        income_stability=IncomeStabilityValue.IRREGULAR,
        dependents_count=3,
        total_life_cover_paise=0,
        monthly_income_paise=50_000_00,
        cash_balance_paise=0,
        essential_monthly_expense_paise=40_000_00,
        total_monthly_emi_paise=45_000_00,
    )
    capacity = compute_capacity_ceiling(inputs)
    assert capacity.ceiling == 1  # worst possible capacity
    result = compute_final_tier(stated, capacity, inputs)

    assert result.final_tier == 1
    assert result.capped is False  # min(1, 1) == stated, nothing was actually capped


# --- the core product scenario: "aggressive" questionnaire answers, but a
# 2-month buffer and heavy EMIs. This must cap the tier, and the cap
# reason + unlock condition must be exact and specific to these numbers. ---


def _core_scenario_capacity():
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("2.00"),  # ceiling 3
        emi_to_income_ratio=Decimal("0.45"),  # ceiling 2 -- heaviest constraint
        income_stability=IncomeStabilityValue.REGULAR,  # ceiling 5, not binding
        dependents_count=0,  # insurance not applicable
        total_life_cover_paise=0,
        monthly_income_paise=100_000_00,  # Rs 1,00,000/month
        cash_balance_paise=200_000_00,  # Rs 2,00,000 cash == 2 months of essential expense
        essential_monthly_expense_paise=100_000_00,  # Rs 1,00,000/month essential expense
        total_monthly_emi_paise=45_000_00,  # Rs 45,000/month EMI == 45% of income
    )
    return inputs, compute_capacity_ceiling(inputs)


def test_core_scenario_aggressive_stated_answers_are_capped_by_capacity():
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)
    assert stated.tier == 5  # "aggressive"

    inputs, capacity = _core_scenario_capacity()
    assert capacity.ceiling == 2

    result = compute_final_tier(stated, capacity, inputs)

    assert result.stated_tier == 5
    assert result.capacity_ceiling == 2
    assert result.final_tier == 2
    assert result.capped is True


def test_core_scenario_binding_constraint_is_exactly_emi_not_buffer():
    # buffer ceiling (3) is worse than unconstrained but is NOT the tightest
    # constraint here -- EMI ratio (ceiling 2) is. The binding-constraint
    # list must name exactly what's binding, not everything that's imperfect.
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)
    inputs, capacity = _core_scenario_capacity()
    result = compute_final_tier(stated, capacity, inputs)

    assert result.binding_constraints == ("emi_to_income_ratio",)
    assert "buffer_months" not in result.binding_constraints


def test_core_scenario_unlock_condition_has_the_exact_computed_numbers():
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)
    inputs, capacity = _core_scenario_capacity()
    result = compute_final_tier(stated, capacity, inputs)

    assert len(result.unlock_conditions) == 1
    unlock = result.unlock_conditions[0]
    assert unlock.constraint == "emi_to_income_ratio"

    # target ceiling = min(stated_tier=5, 5) = 5 -> band requires ratio < 20%
    # required max EMI = floor(0.20 * 100,000_00) = 20,000_00
    # reduction needed = current EMI 45,000_00 - 20,000_00 = 25,000_00 paise = Rs 25,000
    assert "20%" in unlock.message
    assert "Rs 25,000" in unlock.message
    assert unlock.current_value == "45.0%"
    assert unlock.target_value == "below 20%"


def test_tied_constraints_are_all_reported_as_binding():
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)  # tier 5
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("1.50"),  # ceiling 2
        emi_to_income_ratio=Decimal("0.45"),  # ceiling 2 -- tied with buffer
        income_stability=IncomeStabilityValue.REGULAR,
        dependents_count=0,
        total_life_cover_paise=0,
        monthly_income_paise=100_000_00,
        cash_balance_paise=150_000_00,
        essential_monthly_expense_paise=100_000_00,
        total_monthly_emi_paise=45_000_00,
    )
    capacity = compute_capacity_ceiling(inputs)
    assert capacity.ceiling == 2

    result = compute_final_tier(stated, capacity, inputs)
    assert set(result.binding_constraints) == {"buffer_months", "emi_to_income_ratio"}
    assert len(result.unlock_conditions) == 2


def test_income_stability_binding_gives_qualitative_unlock_message():
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("10.00"),  # ceiling 5
        emi_to_income_ratio=Decimal("0.05"),  # ceiling 5
        income_stability=IncomeStabilityValue.IRREGULAR,  # ceiling 3 -- binding
        dependents_count=0,
        total_life_cover_paise=0,
        monthly_income_paise=100_000_00,
        cash_balance_paise=1_000_000_00,
        essential_monthly_expense_paise=100_000_00,
        total_monthly_emi_paise=5_000_00,
    )
    capacity = compute_capacity_ceiling(inputs)
    result = compute_final_tier(stated, capacity, inputs)

    assert result.final_tier == 3
    assert result.binding_constraints == ("income_stability",)
    assert result.unlock_conditions[0].target_value == "regular"


def test_insurance_binding_gives_specific_cover_shortfall():
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS)
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("10.00"),
        emi_to_income_ratio=Decimal("0.05"),
        income_stability=IncomeStabilityValue.REGULAR,
        dependents_count=2,
        total_life_cover_paise=0,  # no cover at all
        monthly_income_paise=100_000_00,
        cash_balance_paise=1_000_000_00,
        essential_monthly_expense_paise=100_000_00,
        total_monthly_emi_paise=5_000_00,
    )
    capacity = compute_capacity_ceiling(inputs)
    assert capacity.ceiling == 1

    result = compute_final_tier(stated, capacity, inputs)
    assert result.binding_constraints == ("insurance_adequacy",)
    unlock = result.unlock_conditions[0]
    # required cover for ceiling 5 = 100% of (income*12*10) = 1,20,00,000_00 paise
    assert "Rs 1,20,00,000" in unlock.message
