import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for import_path in (ROOT, ROOT / "backend"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.services.risk_profile import (
    CapacityInputs,
    IncomeStabilityValue,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1, QUESTIONNAIRE_V2

from research_artifacts.experiments.faithfulness import (
    apply_unlock_condition,
    bootstrap_mean_ci,
    compare_logged_decision,
    replay_logged_decision,
    _suspect_boundary_case,
    _trace_completeness_gap,
    make_explanation_event,
)
from app.services.transparency import build_trace


def _strong_profile_inputs() -> CapacityInputs:
    return CapacityInputs(
        buffer_coverage_months=Decimal("7"),
        emi_to_income_ratio=Decimal("0.1"),
        income_stability=IncomeStabilityValue.REGULAR,
        dependents_count=0,
        total_life_cover_paise=0,
        monthly_income_paise=10_000_000,
        cash_balance_paise=7_000_000,
        essential_monthly_expense_paise=1_000_000,
        total_monthly_emi_paise=1_000_000,
    )


def test_replay_reproduces_pipeline_using_logged_questionnaire_and_finances():
    answers = {
        question.id: question.options[-1].value
        for question in QUESTIONNAIRE_V2.questions
    }
    inputs = _strong_profile_inputs()
    stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
    capacity = compute_capacity_ceiling(inputs)
    final = compute_final_tier(stated, capacity, inputs, CAPACITY_RULE_TABLE_V1)
    suggested = {
        "questionnaire_version": QUESTIONNAIRE_V2.version,
        "answers": answers,
        "stated_tier": final.stated_tier,
        "capacity_ceiling": final.capacity_ceiling,
        "final_tier": final.final_tier,
        "binding_constraints": list(final.binding_constraints),
    }
    context = {
        "buffer_coverage_months": str(inputs.buffer_coverage_months),
        "emi_to_income_ratio": str(inputs.emi_to_income_ratio),
        "income_stability": inputs.income_stability.value,
        "dependents_count": inputs.dependents_count,
        "total_life_cover_paise": inputs.total_life_cover_paise,
        "monthly_income_paise": inputs.monthly_income_paise,
        "cash_balance_paise": inputs.cash_balance_paise,
        "essential_monthly_expense_paise": inputs.essential_monthly_expense_paise,
        "total_monthly_emi_paise": inputs.total_monthly_emi_paise,
    }

    replay = replay_logged_decision(suggested, context)

    assert replay["stated_tier"] == final.stated_tier
    assert replay["capacity_ceiling"] == final.capacity_ceiling
    assert replay["final_tier"] == final.final_tier
    assert replay["binding_constraints"] == list(final.binding_constraints)
    assert compare_logged_decision(suggested, context)[1] == []


def test_legacy_event_missing_replay_inputs_is_marked_as_a_completeness_gap():
    suggested = {
        "questionnaire_version": QUESTIONNAIRE_V2.version,
        "answers": {"horizon": "gt_15y"},
    }
    event = make_explanation_event("legacy", suggested, {})

    trace = build_trace(event)
    replay, mismatches = compare_logged_decision(suggested, {})
    is_gap, gap_fields = _trace_completeness_gap(trace, mismatches)

    assert replay is None
    assert trace.legacy_event is True
    assert trace.schema_version is None
    assert is_gap is True
    assert "replay_not_possible" in gap_fields


def test_emi_unlock_amount_lands_strictly_below_twenty_percent_and_reaches_tier_five():
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("7"),
        emi_to_income_ratio=Decimal("0.45"),
        income_stability=IncomeStabilityValue.REGULAR,
        dependents_count=0,
        total_life_cover_paise=0,
        monthly_income_paise=10_000_000,
        cash_balance_paise=7_000_000,
        essential_monthly_expense_paise=1_000_000,
        total_monthly_emi_paise=4_500_000,
    )
    condition = {
        "constraint": "emi_to_income_ratio",
        "message": "Bring your EMI-to-income ratio below 20% - reduce your monthly EMI outflow by Rs 25,001.",
    }

    updated, error = apply_unlock_condition(inputs, condition)

    assert error is None
    assert updated is not None
    assert updated.total_monthly_emi_paise == 1_999_900
    assert updated.emi_to_income_ratio < Decimal("0.20")
    assert compute_capacity_ceiling(updated).ceiling == 5


def test_task_boundary_case_is_reproduced_by_production_unlock():
    result = _suspect_boundary_case()

    assert result["monthly_income_rupees"] == 100_000
    assert result["monthly_emi_rupees"] == 45_000
    assert result["requested_reduction_rupees"] == 25_001
    assert result["emi_ratio_after"] < result["upper_band_boundary"] == 0.2
    assert result["capacity_ceiling_after"] == 5
    assert result["promised_tier"] == 5
    assert result["unlock_valid"] is True


def test_buffer_insurance_and_stability_instructions_update_only_their_inputs():
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal("1"),
        emi_to_income_ratio=Decimal("0.45"),
        income_stability=IncomeStabilityValue.IRREGULAR,
        dependents_count=1,
        total_life_cover_paise=1_000_000,
        monthly_income_paise=10_000_000,
        cash_balance_paise=1_000_000,
        essential_monthly_expense_paise=1_000_000,
        total_monthly_emi_paise=4_500_000,
    )
    buffer_updated, buffer_error = apply_unlock_condition(
        inputs,
        {"constraint": "buffer_months", "message": "Reach 4 months of emergency buffer."},
    )
    insurance_updated, insurance_error = apply_unlock_condition(
        inputs,
        {
            "constraint": "insurance_adequacy",
            "message": "Increase life insurance cover by Rs 20,000 to reach the target.",
        },
    )
    stability_updated, stability_error = apply_unlock_condition(
        inputs,
        {"constraint": "income_stability", "message": "This cap lifts once income is regular."},
    )

    assert buffer_error is None and buffer_updated is not None
    assert buffer_updated.buffer_coverage_months == Decimal("4")
    assert buffer_updated.cash_balance_paise == 4_000_000
    assert insurance_error is None and insurance_updated is not None
    assert insurance_updated.total_life_cover_paise == 3_000_000
    assert stability_error is None and stability_updated is not None
    assert stability_updated.income_stability == IncomeStabilityValue.REGULAR


def test_bootstrap_mean_interval_is_reproducible_and_contains_mean():
    first = bootstrap_mean_ci([0, 1, 0, 1, 1], seed=17, replicates=250)
    second = bootstrap_mean_ci([0, 1, 0, 1, 1], seed=17, replicates=250)

    assert first == second
    assert first[1] <= first[0] <= first[2]
