"""Pure adapters from synthetic profile records to the production risk APIs."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.services.risk_profile import (
    CapacityInputs,
    IncomeStabilityValue,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import QUESTIONNAIRE_V2


def capacity_inputs_from_profile(profile: dict[str, Any]) -> CapacityInputs:
    """Convert rupee-valued cohort fields to the production paise contract."""
    income = int(profile["monthly_income"])
    essential_expense = int(profile["essential_monthly_expense"])
    monthly_emi = int(profile["total_monthly_emi"])
    if income <= 0 or essential_expense <= 0:
        raise ValueError("monthly income and essential expense must be positive")
    return CapacityInputs(
        buffer_coverage_months=Decimal(int(profile["liquid_cash"])) / Decimal(essential_expense),
        emi_to_income_ratio=Decimal(monthly_emi) / Decimal(income),
        income_stability=IncomeStabilityValue(str(profile["income_stability"])),
        dependents_count=int(profile["dependents_count"]),
        total_life_cover_paise=int(profile["total_life_cover"]) * 100,
        monthly_income_paise=income * 100,
        cash_balance_paise=int(profile["liquid_cash"]) * 100,
        essential_monthly_expense_paise=essential_expense * 100,
        total_monthly_emi_paise=monthly_emi * 100,
    )


def score_profile(profile: dict[str, Any]) -> tuple[int, int]:
    """Return production V2 stated tier and capacity ceiling for a profile."""
    answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
    stated_tier = compute_stated_tier(answers, QUESTIONNAIRE_V2).tier
    capacity = compute_capacity_ceiling(capacity_inputs_from_profile(profile))
    return stated_tier, capacity.ceiling


def compute_method_tiers(profile: dict[str, Any]) -> dict[str, int]:
    """Apply the six requested methods using the existing production rules."""
    inputs = capacity_inputs_from_profile(profile)
    answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
    stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
    capacity = compute_capacity_ceiling(inputs)
    gated = compute_final_tier(stated, capacity, inputs).final_tier

    no_insurance_inputs = replace(inputs, dependents_count=0)
    no_insurance_capacity = compute_capacity_ceiling(no_insurance_inputs)
    no_insurance_tier = compute_final_tier(
        stated,
        no_insurance_capacity,
        no_insurance_inputs,
    ).final_tier

    no_emi_inputs = replace(
        inputs,
        emi_to_income_ratio=Decimal(0),
        total_monthly_emi_paise=0,
    )
    no_emi_capacity = compute_capacity_ceiling(no_emi_inputs)
    no_emi_tier = compute_final_tier(stated, no_emi_capacity, no_emi_inputs).final_tier

    return {
        "willingness_only": stated.tier,
        "ability_only": capacity.ceiling,
        "blend": int(round(0.5 * stated.tier + 0.5 * capacity.ceiling)),
        "gated_min": gated,
        "gated_min_no_insurance": no_insurance_tier,
        "gated_min_no_emi": no_emi_tier,
    }
