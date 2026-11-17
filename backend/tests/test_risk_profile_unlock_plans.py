import re
import sys
from decimal import Decimal
from pathlib import Path

from app.services.risk_profile import (
    CapacityInputs,
    IncomeStabilityValue,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import QUESTIONNAIRE_V2
from app.services.transparency import _risk_outcome_facts, _risk_outcome_summary

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_artifacts.experiments.cohort import COHORT_CONFIG, generate_cohort
from research_artifacts.experiments.common import capacity_inputs_from_profile

AGGRESSIVE_ANSWERS = {
    question.id: question.options[-1].value
    for question in QUESTIONNAIRE_V2.questions
}


def _inputs(**overrides) -> CapacityInputs:
    values = {
        "buffer_coverage_months": Decimal("7"),
        "emi_to_income_ratio": Decimal("0.1"),
        "income_stability": IncomeStabilityValue.REGULAR,
        "dependents_count": 0,
        "total_life_cover_paise": 0,
        "monthly_income_paise": 10_000_000,
        "cash_balance_paise": 7_000_000,
        "essential_monthly_expense_paise": 1_000_000,
        "total_monthly_emi_paise": 1_000_000,
    }
    values.update(overrides)
    return CapacityInputs(**values)


def _apply_displayed_action(inputs: CapacityInputs, action) -> CapacityInputs:
    constraint = action.constraint
    if constraint == "buffer_months":
        months = Decimal(re.search(r"Reach\s+([0-9.]+)\s+months", action.message).group(1))
        cash = max(
            inputs.cash_balance_paise,
            int(months * Decimal(inputs.essential_monthly_expense_paise)),
        )
        return CapacityInputs(
            **{
                **inputs.__dict__,
                "buffer_coverage_months": months,
                "cash_balance_paise": cash,
            }
        )
    match = re.search(r"\bRs\s+([\d,]+)", action.message)
    amount_paise = int(match.group(1).replace(",", "")) * 100
    if constraint == "emi_to_income_ratio":
        emi = max(0, inputs.total_monthly_emi_paise - amount_paise)
        return CapacityInputs(
            **{
                **inputs.__dict__,
                "total_monthly_emi_paise": emi,
                "emi_to_income_ratio": Decimal(emi) / Decimal(inputs.monthly_income_paise),
            }
        )
    if constraint == "insurance_adequacy":
        return CapacityInputs(
            **{
                **inputs.__dict__,
                "total_life_cover_paise": inputs.total_life_cover_paise + amount_paise,
            }
        )
    raise AssertionError(f"unexpected user-changeable action: {constraint}")


def _result(inputs: CapacityInputs):
    stated = compute_stated_tier(AGGRESSIVE_ANSWERS, QUESTIONNAIRE_V2)
    return compute_final_tier(stated, compute_capacity_ceiling(inputs), inputs)


def test_100000_income_45000_emi_displayed_reduction_reaches_tier_five():
    inputs = _inputs(
        emi_to_income_ratio=Decimal("0.45"),
        total_monthly_emi_paise=4_500_000,
    )
    result = _result(inputs)
    action = next(a for a in result.unlock_conditions if a.constraint == "emi_to_income_ratio")
    updated = _apply_displayed_action(inputs, action)

    assert "Rs 25,001" in action.message
    assert updated.emi_to_income_ratio < Decimal("0.20")
    assert compute_capacity_ceiling(updated).ceiling == 5


def test_joint_plan_reaches_target_when_single_tied_actions_do_not():
    inputs = _inputs(
        buffer_coverage_months=Decimal("1.5"),
        emi_to_income_ratio=Decimal("0.45"),
        cash_balance_paise=1_500_000,
        total_monthly_emi_paise=4_500_000,
    )
    result = _result(inputs)

    assert set(result.binding_constraints) == {"buffer_months", "emi_to_income_ratio"}
    assert len(result.joint_unlock_plan) == 2
    for action in result.joint_unlock_plan:
        updated = _apply_displayed_action(inputs, action)
        assert compute_capacity_ceiling(updated).ceiling < result.achievable_tier

    jointly_updated = inputs
    for action in result.joint_unlock_plan:
        jointly_updated = _apply_displayed_action(jointly_updated, action)
    assert compute_capacity_ceiling(jointly_updated).ceiling >= result.achievable_tier == 5
    data = {
        "stated_tier": result.stated_tier,
        "final_tier": result.final_tier,
        "capped": result.capped,
        "binding_constraints": list(result.binding_constraints),
        "unlock_conditions": [condition.__dict__ for condition in result.unlock_conditions],
        "joint_unlock_plan": [action.__dict__ for action in result.joint_unlock_plan],
        "achievable_tier": result.achievable_tier,
        "blocking_constraints": list(result.blocking_constraints),
    }
    plan_fact = next(
        fact for fact in _risk_outcome_facts(data, {}) if fact.label == "Joint unlock plan"
    )
    assert "you need to do all of the following" in plan_fact.value.lower()


def test_irregular_income_reports_reachable_tier_and_blocker():
    result = _result(_inputs(income_stability=IncomeStabilityValue.IRREGULAR))
    data = {
        "stated_tier": result.stated_tier,
        "final_tier": result.final_tier,
        "capped": result.capped,
        "binding_constraints": list(result.binding_constraints),
        "unlock_conditions": [condition.__dict__ for condition in result.unlock_conditions],
        "joint_unlock_plan": [action.__dict__ for action in result.joint_unlock_plan],
        "achievable_tier": result.achievable_tier,
        "blocking_constraints": list(result.blocking_constraints),
    }
    text = " ".join(
        [_risk_outcome_summary(data, {}), *(fact.value for fact in _risk_outcome_facts(data, {}))]
    )

    assert result.achievable_tier == 3
    assert result.blocking_constraints == ("income_stability",)
    assert "Tier 3" in text
    assert "Tier 5" in text
    assert "steady your income" in text.lower()


def test_joint_plan_reaches_achievable_tier_for_two_thousand_seeded_profiles():
    profiles = generate_cohort(
        n_profiles=2000,
        seed=int(COHORT_CONFIG["seed"]),
    )
    for profile in profiles:
        profile_inputs = capacity_inputs_from_profile(profile)
        answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
        result = compute_final_tier(
            compute_stated_tier(answers, QUESTIONNAIRE_V2),
            compute_capacity_ceiling(profile_inputs),
            profile_inputs,
        )
        updated = profile_inputs
        for action in result.joint_unlock_plan:
            updated = _apply_displayed_action(updated, action)
        assert compute_capacity_ceiling(updated).ceiling >= result.achievable_tier, profile["profile_id"]
