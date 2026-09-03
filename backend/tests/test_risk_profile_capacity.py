from decimal import Decimal

import pytest

from app.services.risk_profile import CapacityInputs, IncomeStabilityValue, compute_capacity_ceiling


def _inputs(**overrides):
    defaults = dict(
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
    defaults.update(overrides)
    return CapacityInputs(**defaults)


def test_fully_unconstrained_inputs_give_ceiling_5():
    result = compute_capacity_ceiling(_inputs())
    assert result.ceiling == 5
    assert {c.name: c.ceiling for c in result.components} == {
        "buffer_months": 5,
        "emi_to_income_ratio": 5,
        "income_stability": 5,
        "insurance_adequacy": 5,
    }


@pytest.mark.parametrize(
    "buffer_months,expected_ceiling",
    [
        (Decimal("0.00"), 1),
        (Decimal("0.99"), 1),
        (Decimal("1.00"), 2),
        (Decimal("1.99"), 2),
        (Decimal("2.00"), 3),
        (Decimal("3.99"), 3),
        (Decimal("4.00"), 4),
        (Decimal("5.99"), 4),
        (Decimal("6.00"), 5),
        (Decimal("50.00"), 5),
    ],
)
def test_buffer_band_boundaries(buffer_months, expected_ceiling):
    result = compute_capacity_ceiling(_inputs(buffer_coverage_months=buffer_months))
    buffer_component = next(c for c in result.components if c.name == "buffer_months")
    assert buffer_component.ceiling == expected_ceiling


@pytest.mark.parametrize(
    "ratio,expected_ceiling",
    [
        (Decimal("0.19"), 5),
        (Decimal("0.20"), 4),
        (Decimal("0.29"), 4),
        (Decimal("0.30"), 3),
        (Decimal("0.39"), 3),
        (Decimal("0.40"), 2),
        (Decimal("0.49"), 2),
        (Decimal("0.50"), 1),
        (Decimal("0.90"), 1),
    ],
)
def test_emi_to_income_band_boundaries(ratio, expected_ceiling):
    result = compute_capacity_ceiling(_inputs(emi_to_income_ratio=ratio))
    emi_component = next(c for c in result.components if c.name == "emi_to_income_ratio")
    assert emi_component.ceiling == expected_ceiling


def test_irregular_income_caps_at_3_even_if_everything_else_is_fine():
    result = compute_capacity_ceiling(_inputs(income_stability=IncomeStabilityValue.IRREGULAR))
    stability_component = next(c for c in result.components if c.name == "income_stability")
    assert stability_component.ceiling == 3
    assert result.ceiling == 3


def test_insurance_not_applicable_with_zero_dependents():
    result = compute_capacity_ceiling(_inputs(dependents_count=0, total_life_cover_paise=0))
    insurance_component = next(c for c in result.components if c.name == "insurance_adequacy")
    assert insurance_component.applicable is False
    assert result.ceiling == 5  # zero cover doesn't matter without dependents


def test_insurance_adequacy_with_dependents_and_no_cover():
    # required cover = income * 12 * 10 = 100,000_00 * 12 * 10 = 120,000,000_00
    result = compute_capacity_ceiling(_inputs(dependents_count=2, total_life_cover_paise=0))
    insurance_component = next(c for c in result.components if c.name == "insurance_adequacy")
    assert insurance_component.applicable is True
    assert insurance_component.ceiling == 1
    assert result.ceiling == 1


def test_insurance_adequacy_fully_covered():
    required_cover = 100_000_00 * 12 * 10
    result = compute_capacity_ceiling(_inputs(dependents_count=2, total_life_cover_paise=required_cover))
    insurance_component = next(c for c in result.components if c.name == "insurance_adequacy")
    assert insurance_component.ceiling == 5


def test_overall_ceiling_is_the_minimum_of_applicable_components():
    result = compute_capacity_ceiling(
        _inputs(
            buffer_coverage_months=Decimal("2.00"),  # ceiling 3
            emi_to_income_ratio=Decimal("0.45"),  # ceiling 2
            income_stability=IncomeStabilityValue.REGULAR,  # ceiling 5
            dependents_count=0,  # not applicable
        )
    )
    assert result.ceiling == 2
