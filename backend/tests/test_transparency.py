import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import HoldingType
from app.services.debt_leak_service import compute_and_log_debt_leak_report
from app.services.event_log import log_suggestion_event
from app.services.financial_position import ExpenseFrequency
from app.services.onboarding import add_emi, add_expense_item, add_holding, upsert_profile
from app.services.personalization_service import compute_and_log_personalization, record_allocation_outcome
from app.services.personalization import EditActionTaken
from app.services.risk_profile_service import compute_and_log_risk_tier
from app.services.transparency import (
    DECISION_TYPES,
    FRAMING_LABEL,
    NoSuchDecisionEventError,
    UnknownDecisionTypeError,
    get_trace,
    list_available_decision_types,
)

USER = "transparency-user-1"

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
}


def _full_onboarding(session):
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=800_000_00,
    )
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_holding(session, user_id=USER, description="Equity fund", value_paise=100_000_00, holding_type=HoldingType.EQUITY_MUTUAL_FUND)
    add_emi(session, user_id=USER, lender="Personal Loan Co", amount_paise=10_000_00, remaining_tenure_months=24, annual_rate_bps=1500)
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)
    compute_and_log_allocation(session, USER)
    compute_and_log_debt_leak_report(session, USER)
    compute_and_log_personalization(session, USER)


def test_unknown_decision_type_raises(session):
    with pytest.raises(UnknownDecisionTypeError):
        get_trace(session, USER, "not_a_real_decision_type")


def test_no_event_yet_raises(session):
    with pytest.raises(NoSuchDecisionEventError):
        get_trace(session, USER, "risk_profile")


def test_risk_profile_trace_reconstructs_purely_from_stored_data(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "risk_profile")

    assert trace.gap_detected is False
    assert trace.framing_label == FRAMING_LABEL
    assert trace.reasoning["questionnaire"]["answers"] == AGGRESSIVE_ANSWERS
    assert trace.reasoning["capacity_layer"]["objective_inputs"]["income_stability"] == "regular"
    assert "final tier" in trace.headline.lower() or "tier" in trace.headline.lower()


def test_allocation_trace_names_which_tier_and_which_rule(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "allocation")

    assert trace.gap_detected is False
    assert trace.reasoning["which_tier"] == 5
    assert trace.reasoning["which_rule"] == "v1"
    assert "target_pct" in trace.reasoning
    assert trace.reasoning["per_holding_classification"]  # holdings present, not description text
    for h in trace.reasoning["per_holding_classification"]:
        assert "description" not in h  # Module 4's hard constraint still holds through this view


def test_debt_leak_trace_carries_itemized_components(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "debt_leak_engine")

    assert trace.gap_detected is False
    assert isinstance(trace.reasoning["itemized_components"], list)
    assert "statement parser" in trace.reasoning["data_source_note"]


def test_personalization_trace_carries_step_by_step_trace(session):
    _full_onboarding(session)
    allocation_event = get_trace(session, USER, "allocation")
    record_allocation_outcome(
        session, USER, allocation_event.event_id, action_taken=EditActionTaken.EDITED,
        chosen_target_pct={"cash": "0", "debt": "10", "equity": "80", "real_assets": "5", "alternatives": "5"}, funded=True,
    )
    compute_and_log_personalization(session, USER)

    trace = get_trace(session, USER, "personalization")
    assert trace.gap_detected is False
    assert len(trace.reasoning["step_by_step_trace"]) >= 1


def test_all_decision_types_use_the_transparent_reasoning_label_never_ai(session):
    _full_onboarding(session)
    for module_source in DECISION_TYPES:
        trace = get_trace(session, USER, module_source)
        assert trace.framing_label == "transparent reasoning"
        assert "ai" not in trace.framing_label.lower()
        assert "explainable" not in trace.framing_label.lower()


def test_list_available_decision_types_reflects_what_has_been_computed(session):
    assert list_available_decision_types(session, USER) == {}
    _full_onboarding(session)
    available = list_available_decision_types(session, USER)
    assert set(available) == {"risk_profile", "allocation", "debt_leak_engine", "personalization"}
    assert all(count >= 1 for count in available.values())


# --- the gap-detection mechanism: a module that doesn't store enough
# must be flagged, not silently faked ---


def test_incomplete_stored_event_is_flagged_as_a_gap_not_fabricated(session):
    # simulates an older/incomplete risk_profile event missing fields the
    # decision-type spec requires -- this must never be silently
    # backfilled with a freshly recomputed value
    log_suggestion_event(
        session,
        user_id=USER,
        module_source="risk_profile",
        suggested_value={"stated_tier": 5, "final_tier": 3},  # missing most required keys
        market_context={},
    )

    trace = get_trace(session, USER, "risk_profile")

    assert trace.gap_detected is True
    assert "capacity_ceiling" in trace.missing_fields
    assert "buffer_coverage_months" in trace.missing_fields
    assert "Cannot fully reconstruct" in trace.headline
    # what IS present is still surfaced, not discarded
    assert trace.reasoning["partial_suggested_value"]["stated_tier"] == 5


def test_complete_event_is_never_flagged_as_a_gap(session):
    _full_onboarding(session)
    for module_source in DECISION_TYPES:
        trace = get_trace(session, USER, module_source)
        assert trace.gap_detected is False
        assert trace.missing_fields == ()
