"""Wires Module 3's pure risk-profiling logic to Module 2's data (buffer
months, EMI ratio, income stability, insurance-vs-dependents) and Module
1's event log. This is the only layer in Module 3 that touches the
database — everything it calls into (compute_stated_tier,
compute_capacity_ceiling, compute_final_tier) is pure and independently
tested in tests/test_risk_profile_*.py.
"""

import dataclasses
import logging

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
    stated_tier_from_ml_estimate,
)
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1, QUESTIONNAIRE_V2, CapacityRuleTable, Questionnaire
from app.services.risk_profile_ml import (
    FEATURE_ORDER_REDUCED,
    MODEL_PATH_REDUCED,
    MODEL_VERSION_REDUCED,
    MLModelUnavailableError,
    predict_with_explanation,
)

logger = logging.getLogger(__name__)


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
    questionnaire: Questionnaire = QUESTIONNAIRE_V2,
    rule_table: CapacityRuleTable = CAPACITY_RULE_TABLE_V1,
    commit: bool = True,
) -> FinalTierResult:
    all_question_ids = {q.id for q in questionnaire.questions}
    answered_ids = set(answers)
    # Exactly two valid shapes: all 7 (full/deterministic), or exactly the
    # 4 required ones and no others (quick mode). Anything in between (e.g.
    # 6 of 7, or the 4 required plus one extra) is treated as an error
    # rather than silently guessed at -- it's ambiguous whether the caller
    # meant to submit quick mode and over-included an answer, or meant full
    # mode and is missing one, and guessing wrong either way would either
    # silently discard a real answer or silently accept an incomplete
    # deterministic score.
    quick_mode = answered_ids == set(FEATURE_ORDER_REDUCED)

    quick_prediction = None
    if not (all_question_ids - answered_ids):
        stated = compute_stated_tier(answers, questionnaire)
    elif quick_mode:
        # Quick mode: the user answered only the 4 "main" questions this
        # reduced model was trained on. There is no deterministic formula
        # to fall back to over a partial answer set (compute_stated_tier
        # requires all 7) -- this prediction *is* the stated tier, not a
        # secondary opinion on one, which is the whole point of letting a
        # user skip 3 questions. Deliberately not caught here: if the
        # reduced model can't load, there is no tier to compute at all, so
        # this must propagate (the route layer maps it to a clear error),
        # unlike the full-mode ML call below, which is only ever a bonus
        # explanation and must never block the user's actual submission.
        quick_prediction = predict_with_explanation(
            answers,
            questionnaire,
            feature_order=FEATURE_ORDER_REDUCED,
            model_path=MODEL_PATH_REDUCED,
            model_version=MODEL_VERSION_REDUCED,
        )
        stated = stated_tier_from_ml_estimate(quick_prediction.predicted_tier, quick_prediction.model_version, questionnaire.version)
    else:
        missing = sorted(all_question_ids - answered_ids)
        raise ValueError(f"missing answers for questions: {missing}")

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
            "estimation_method": stated.estimation_method,
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

    if quick_mode:
        # quick_prediction above already *is* the decision source -- logged
        # under risk_profile_ml too (is_authoritative=True) so Module 9's
        # transparency view can still show "why this tier" with the same
        # SHAP feature-contribution detail a full-7 submission gets.
        log_suggestion_event(
            session,
            user_id=user_id,
            module_source="risk_profile_ml",
            tier=str(quick_prediction.predicted_tier),
            suggested_value={
                "model_version": quick_prediction.model_version,
                "predicted_tier": quick_prediction.predicted_tier,
                "class_probabilities": quick_prediction.class_probabilities,
                "feature_contributions": [dataclasses.asdict(c) for c in quick_prediction.feature_contributions],
                "questionnaire_version": questionnaire.version,
                "answers": answers,
                "static_final_tier": final.final_tier,
                "is_authoritative": True,
            },
            commit=commit,
        )
        return final

    # Module 3b: a second, independent prediction from a trained model, on
    # the same answers. Best-effort -- a missing/unloadable model (or a
    # dev machine without the ML extras installed) must never break the
    # user's actual, authoritative static risk-tier submission above.
    try:
        ml_result = predict_with_explanation(answers, questionnaire)
    except (MLModelUnavailableError, ValueError):
        logger.warning("risk_profile_ml prediction unavailable for user_id=%r", user_id, exc_info=True)
    else:
        log_suggestion_event(
            session,
            user_id=user_id,
            module_source="risk_profile_ml",
            tier=str(ml_result.predicted_tier),
            suggested_value={
                "model_version": ml_result.model_version,
                "predicted_tier": ml_result.predicted_tier,
                "class_probabilities": ml_result.class_probabilities,
                "feature_contributions": [dataclasses.asdict(c) for c in ml_result.feature_contributions],
                # carried alongside so the trace can show "what a person
                # with these answers reads" the same way Module 3's does,
                # without this module needing its own copy of the labels.
                "questionnaire_version": questionnaire.version,
                "answers": answers,
                # so the trace can say "the rule-based engine agreed/disagreed"
                "static_final_tier": final.final_tier,
                "is_authoritative": False,
            },
            commit=commit,
        )

    return final
