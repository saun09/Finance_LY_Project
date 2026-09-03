"""Wires Module 3's pure risk-profiling logic to Module 2's data (buffer
months, EMI ratio, income stability, insurance-vs-dependents) and Module
1's event log. This is the only layer in Module 3 that touches the
database — everything it calls into (compute_stated_tier,
compute_capacity_ceiling, compute_final_tier) is pure and independently
tested in tests/test_risk_profile_*.py.
"""

import dataclasses

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import InsurancePolicy, InsuranceType
from app.services.event_log import log_suggestion_event
from app.services.onboarding import ProfileNotFoundError, compute_financial_position, get_profile
from app.services.risk_profile import (
    CapacityInputs,
    FinalTierResult,
    IncomeStabilityValue,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1, QUESTIONNAIRE_V1, CapacityRuleTable, Questionnaire


def gather_capacity_inputs(session: Session, user_id: str) -> CapacityInputs:
    profile = get_profile(session, user_id)
    if profile is None:
        raise ProfileNotFoundError(f"no user_profile for user_id={user_id!r}; complete Module 2 onboarding first")
    position = compute_financial_position(session, user_id)

    total_life_cover_paise = session.execute(
        select(InsurancePolicy.sum_assured_paise).where(
            InsurancePolicy.user_id == user_id, InsurancePolicy.policy_type == InsuranceType.LIFE
        )
    ).scalars().all()

    return CapacityInputs(
        buffer_coverage_months=position["buffer_coverage_months"],
        emi_to_income_ratio=position["emi_to_income_ratio"],
        income_stability=IncomeStabilityValue(profile.income_stability.value),
        dependents_count=profile.dependents_count,
        total_life_cover_paise=sum(total_life_cover_paise),
        monthly_income_paise=profile.income_paise,
        cash_balance_paise=profile.cash_balance_paise,
        essential_monthly_expense_paise=position["essential_monthly_expense_paise"],
        total_monthly_emi_paise=position["total_monthly_emi_paise"],
    )


def compute_and_log_risk_tier(
    session: Session,
    user_id: str,
    answers: dict[str, str],
    questionnaire: Questionnaire = QUESTIONNAIRE_V1,
    rule_table: CapacityRuleTable = CAPACITY_RULE_TABLE_V1,
    commit: bool = True,
) -> FinalTierResult:
    stated = compute_stated_tier(answers, questionnaire)
    inputs = gather_capacity_inputs(session, user_id)
    capacity = compute_capacity_ceiling(inputs, rule_table)
    final = compute_final_tier(stated, capacity, inputs, rule_table)

    log_suggestion_event(
        session,
        user_id=user_id,
        module_source="risk_profile",
        tier=str(final.final_tier),
        suggested_value={
            "answers": answers,
            "questionnaire_version": stated.questionnaire_version,
            "stated_score": stated.score,
            "stated_tier": stated.tier,
            "rule_table_version": capacity.rule_table_version,
            "capacity_ceiling": capacity.ceiling,
            "capacity_components": [dataclasses.asdict(c) for c in capacity.components],
            "final_tier": final.final_tier,
            "capped": final.capped,
            "binding_constraints": list(final.binding_constraints),
            "unlock_conditions": [dataclasses.asdict(u) for u in final.unlock_conditions],
        },
        # reused as a general "objective inputs at computation time" snapshot,
        # per Module 1's field: JSON context for a later transparency view to
        # explain "why this, then" -- not literal market data here.
        market_context={
            "buffer_coverage_months": str(inputs.buffer_coverage_months),
            "emi_to_income_ratio": str(inputs.emi_to_income_ratio),
            "income_stability": inputs.income_stability.value,
            "dependents_count": inputs.dependents_count,
            "total_life_cover_paise": inputs.total_life_cover_paise,
            "monthly_income_paise": inputs.monthly_income_paise,
            "cash_balance_paise": inputs.cash_balance_paise,
            "essential_monthly_expense_paise": inputs.essential_monthly_expense_paise,
            "total_monthly_emi_paise": inputs.total_monthly_emi_paise,
        },
        commit=commit,
    )

    return final
