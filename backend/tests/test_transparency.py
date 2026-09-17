import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.models.suggestion_event import ActionTaken
from app.services.allocation_config import CONFIG_VERSION as ALLOCATION_CONFIG_VERSION
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import HoldingType
from app.services.debt_leak_service import compute_and_log_debt_leak_report
from app.services.event_log import log_suggestion_event
from app.services.financial_position import ExpenseFrequency
from app.services.gamification_service import check_milestones
from app.services.onboarding import add_emi, add_expense_item, add_holding, upsert_profile
from app.services.personalization import EditActionTaken
from app.services.personalization_service import compute_and_log_personalization, record_allocation_outcome
from app.services.risk_profile_service import compute_and_log_risk_tier
from app.services.transparency import (
    ALLOWED_FRAMING_LABELS,
    CONTEST_REASON_CODES,
    DECISION_TYPES,
    FRAMING_LABEL,
    RETRIEVAL_EXPLANATION_LABEL,
    THIRD_PARTY_OUTPUT_LABEL,
    UNAVAILABLE_KEY,
    InvalidContestReasonError,
    NoSuchDecisionEventError,
    UnknownDecisionTypeError,
    build_value_hints,
    compare_traces,
    contest_decision,
    get_trace,
    list_available_decision_types,
    list_decision_events,
)

USER = "transparency-user-1"

# All seven QUESTIONNAIRE_V2 questions answered at maximum points, so the
# stated tier is unambiguously the top one and any cap the user ends up with
# came from the capacity layer, not from a middling questionnaire score.
AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
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
    assert "tier" in trace.headline.lower()


def test_allocation_trace_names_which_tier_and_which_rule(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "allocation")

    assert trace.gap_detected is False
    assert trace.reasoning["rule_lookup"]["which_tier"] == 5
    assert trace.reasoning["rule_lookup"]["which_rule"] == "v3-hybrid"
    assert "target_pct" in trace.reasoning["rule_lookup"]
    assert trace.reasoning["current_position"]["per_holding_classification"]  # holdings present, not description text
    for h in trace.reasoning["current_position"]["per_holding_classification"]:
        assert "description" not in h  # Module 4's hard constraint still holds through this view


def test_debt_leak_trace_carries_itemized_components(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "debt_leak_engine")

    assert trace.gap_detected is False
    assert isinstance(trace.reasoning["recoverable_total"]["itemized_components"], list)
    assert "statement parser" in trace.reasoning["data_provenance"]["data_source_note"]


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


# --- labeling: the two claims this module makes are never conflated ---


def test_rule_table_decision_types_use_transparent_reasoning_never_ai(session):
    """Modules 3/4/6/7/10 are weighted sums and table lookups. Printing the
    weights is the whole feature; calling it explainable AI would overclaim."""
    rule_table_types = ("risk_profile", "allocation", "debt_leak_engine", "personalization", "gamification")
    for module_source in rule_table_types:
        spec = DECISION_TYPES[module_source]
        assert spec.framing_label == "transparent reasoning"
        assert "ai" not in spec.framing_label.lower().split()
        assert "explainable" not in spec.framing_label.lower()


def test_the_two_module_5_engines_carry_different_claims(session):
    """The explainability claim belongs to the local constrained-retrieval
    engine, which can name the constraint that eliminated each candidate.
    The n8n workflow returns its own prose and must never borrow that claim."""
    assert DECISION_TYPES["rumour_verification_local"].framing_label == RETRIEVAL_EXPLANATION_LABEL
    assert DECISION_TYPES["rumour_verification"].framing_label == THIRD_PARTY_OUTPUT_LABEL
    assert DECISION_TYPES["rumour_verification"].claim_note is not None
    assert "self-report" in DECISION_TYPES["rumour_verification"].claim_note


def test_no_spec_may_claim_ai_or_explainable_ai(session):
    for spec in DECISION_TYPES.values():
        label = spec.framing_label.lower()
        assert spec.framing_label in ALLOWED_FRAMING_LABELS
        assert "ai" not in label.split()
        assert "explainable ai" not in label


# --- gap detection: value-aware, and degrading per section ---


def test_incomplete_stored_event_is_flagged_as_a_gap_not_fabricated(session):
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
    assert trace.reasoning["capacity_layer"][UNAVAILABLE_KEY] is True
    assert trace.reasoning["questionnaire"]["recorded_values"]["stated_tier"] == 5


def test_a_null_valued_key_counts_as_missing_not_as_a_recorded_value(session):
    """Presence-only checking would render `final_tier: null` as
    'stated tier 5 -> final tier None', which reads like a real trace but
    explains nothing. A null is an absent recording, not a decision."""
    log_suggestion_event(
        session,
        user_id=USER,
        module_source="gamification",
        suggested_value={"milestone_id": "buffer_3", "category": "buffer", "headline": None, "details": {}},
        market_context={"config_version": "v1"},
    )
    trace = get_trace(session, USER, "gamification")
    assert trace.gap_detected is True
    assert "headline" in trace.missing_fields


def test_one_missing_field_degrades_only_its_own_section(session):
    """An older event missing `unlock_conditions` must still show the
    questionnaire and capacity blocks that WERE recorded properly --
    all-or-nothing degradation throws away good evidence."""
    _full_onboarding(session)
    good = get_trace(session, USER, "risk_profile")
    stored = dict(good.reasoning)  # sanity: everything available first
    assert all(s.available for s in good.sections)

    complete_event_value = {
        "answers": AGGRESSIVE_ANSWERS,
        "questionnaire_version": "v2",
        "stated_score": 100,
        "stated_tier": 5,
        "rule_table_version": "v1",
        "capacity_ceiling": 3,
        "capacity_components": [],
        "final_tier": 3,
        "capped": True,
        "binding_constraints": ["buffer"],
        # unlock_conditions deliberately omitted
    }
    log_suggestion_event(
        session,
        user_id=USER,
        module_source="risk_profile",
        suggested_value=complete_event_value,
        market_context=stored["capacity_layer"]["objective_inputs"],
    )

    trace = get_trace(session, USER, "risk_profile")
    by_key = {s.key: s for s in trace.sections}

    assert trace.gap_detected is True
    assert trace.missing_fields == ("unlock_conditions",)
    assert by_key["questionnaire"].available is True
    assert by_key["capacity_layer"].available is True
    assert by_key["outcome"].available is False
    # the good sections rendered fully
    assert trace.reasoning["questionnaire"]["answers"] == AGGRESSIVE_ANSWERS
    assert trace.reasoning["capacity_layer"]["capacity_ceiling"] == 3
    # the bad one degraded but still shows what it had
    assert trace.reasoning["outcome"][UNAVAILABLE_KEY] is True
    assert trace.reasoning["outcome"]["recorded_values"]["binding_constraints"] == ["buffer"]
    # the headline still works, because its own inputs were all present
    assert "Cannot fully reconstruct" not in trace.headline


def test_empty_list_is_a_real_recorded_value_not_a_gap(session):
    """`binding_constraints: []` legitimately means 'nothing was binding'."""
    log_suggestion_event(
        session,
        user_id=USER,
        module_source="risk_profile",
        suggested_value={
            "answers": AGGRESSIVE_ANSWERS, "questionnaire_version": "v2", "stated_score": 100,
            "stated_tier": 5, "rule_table_version": "v1", "capacity_ceiling": 5,
            "capacity_components": [], "final_tier": 5, "capped": False,
            "binding_constraints": [], "unlock_conditions": [],
        },
        market_context={
            "buffer_coverage_months": "40", "emi_to_income_ratio": "0.1", "income_stability": "regular",
            "dependents_count": 0, "total_life_cover_paise": 0, "monthly_income_paise": 100_000_00,
        },
    )
    trace = get_trace(session, USER, "risk_profile")
    assert trace.gap_detected is False
    assert trace.reasoning["outcome"]["binding_constraints"] == []


def test_complete_event_is_never_flagged_as_a_gap(session):
    _full_onboarding(session)
    for module_source in ("risk_profile", "allocation", "debt_leak_engine", "personalization"):
        trace = get_trace(session, USER, module_source)
        assert trace.gap_detected is False, f"{module_source}: {trace.missing_fields}"
        assert trace.missing_fields == ()


# --- Module 10 is traceable too ---


def test_gamification_milestones_are_traceable(session):
    _full_onboarding(session)
    awarded = check_milestones(session, USER)
    assert awarded, "fixture should cross at least one buffer threshold"

    trace = get_trace(session, USER, "gamification")
    assert trace.gap_detected is False
    assert trace.framing_label == FRAMING_LABEL
    assert trace.reasoning["threshold_rule"]["milestone_id"]
    assert "threshold_inputs" in trace.reasoning["threshold_rule"]


# --- index counts ---


def test_list_available_decision_types_reflects_what_has_been_computed(session):
    assert list_available_decision_types(session, USER) == {}
    _full_onboarding(session)
    available = list_available_decision_types(session, USER)
    assert set(available) == {"risk_profile", "allocation", "debt_leak_engine", "personalization"}
    assert all(count >= 1 for count in available.values())


def test_counts_are_exact_beyond_any_fetch_limit(session):
    """The count is shown to the user as 'how many decisions of this kind you
    have', so it must be a real COUNT, not len() of a capped fetch."""
    for i in range(7):
        log_suggestion_event(
            session, user_id=USER, module_source="gamification",
            suggested_value={"milestone_id": f"m{i}", "category": "buffer", "headline": "h", "details": {}},
            market_context={"config_version": "v1"},
        )
    assert list_available_decision_types(session, USER)["gamification"] == 7


def test_counts_do_not_leak_between_users(session):
    log_suggestion_event(
        session, user_id="someone-else", module_source="gamification",
        suggested_value={"milestone_id": "m", "category": "buffer", "headline": "h", "details": {}},
        market_context={"config_version": "v1"},
    )
    assert list_available_decision_types(session, USER) == {}


# --- history and comparison ---


def test_decision_history_lists_every_recorded_decision_newest_first(session):
    _full_onboarding(session)
    compute_and_log_risk_tier(session, USER, {**AGGRESSIVE_ANSWERS, "horizon": "lt_1y"})

    history = list_decision_events(session, USER, "risk_profile")
    assert len(history) == 2
    assert history[0].timestamp >= history[1].timestamp
    assert all(h.module_source == "risk_profile" for h in history)
    assert all(h.headline for h in history)


def test_comparison_names_which_stored_input_moved(session):
    _full_onboarding(session)
    first = list_decision_events(session, USER, "risk_profile")[0]
    compute_and_log_risk_tier(session, USER, {**AGGRESSIVE_ANSWERS, "horizon": "lt_1y"})
    second = list_decision_events(session, USER, "risk_profile")[0]

    comparison = compare_traces(session, USER, "risk_profile", first.event_id, second.event_id)

    changed_paths = {c.path for c in comparison.changes}
    assert "questionnaire.answers.horizon" in changed_paths
    horizon = next(c for c in comparison.changes if c.path == "questionnaire.answers.horizon")
    assert horizon.before == "gt_15y"
    assert horizon.after == "lt_1y"
    assert comparison.unchanged_field_count > 0  # unchanged fields are not reported as changes


def test_comparison_refuses_an_event_belonging_to_another_user(session):
    _full_onboarding(session)
    mine = list_decision_events(session, USER, "risk_profile")[0]
    theirs = log_suggestion_event(
        session, user_id="someone-else", module_source="risk_profile",
        suggested_value={"stated_tier": 1, "final_tier": 1}, market_context={},
    )
    with pytest.raises(NoSuchDecisionEventError):
        compare_traces(session, USER, "risk_profile", mine.event_id, theirs.event_id)


# --- value hints ---


def test_value_hints_declare_units_without_altering_stored_values(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "debt_leak_engine")

    assert trace.value_hints["total_recoverable_annual_paise"] == "paise"
    assert trace.value_hint_rules_version
    # the raw stored integer is untouched -- hints add, they never substitute
    raw = trace.reasoning["recoverable_total"]["total_recoverable_annual_paise"]
    assert isinstance(raw, int)


def test_value_hint_table_prefers_the_more_specific_suffix():
    hints = build_value_hints({"offset_pct_points": "2.5", "target_pct": "40", "value_paise": 100})
    assert hints["offset_pct_points"] == "percent_points"
    assert hints["target_pct"] == "percent"
    assert hints["value_paise"] == "paise"


def test_plain_text_leaves_get_no_hint():
    assert build_value_hints({"income_stability": "regular", "capped": True}) == {}


# --- contest ---


def test_contesting_a_decision_records_it_through_module_1s_event_log(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "risk_profile")
    assert trace.contested is False

    updated = contest_decision(
        session, USER, "risk_profile", trace.event_id, "input_wrong", note="My buffer is bigger than this",
    )

    assert updated.contested is True
    assert updated.contest_reason_code == "input_wrong"
    # written where Module 7 already looks, not into a parallel store
    from app.models.suggestion_event import SuggestionEvent

    event = session.get(SuggestionEvent, trace.event_id)
    assert event.action_taken == ActionTaken.REJECTED
    assert event.delta["contest_note"] == "My buffer is bigger than this"
    assert event.delta["contested_via"] == "transparency_trace"


def test_contest_rejects_a_reason_code_outside_the_closed_set(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "risk_profile")
    with pytest.raises(InvalidContestReasonError):
        contest_decision(session, USER, "risk_profile", trace.event_id, "because_i_said_so")


def test_contest_refuses_another_users_event(session):
    theirs = log_suggestion_event(
        session, user_id="someone-else", module_source="risk_profile",
        suggested_value={"stated_tier": 1, "final_tier": 1}, market_context={},
    )
    with pytest.raises(NoSuchDecisionEventError):
        contest_decision(session, USER, "risk_profile", theirs.event_id, "input_wrong")


def test_contested_flag_shows_up_in_history(session):
    _full_onboarding(session)
    trace = get_trace(session, USER, "risk_profile")
    contest_decision(session, USER, "risk_profile", trace.event_id, "rule_wrong")

    history = list_decision_events(session, USER, "risk_profile")
    assert history[0].contested is True


def test_contest_reason_codes_are_a_small_closed_set():
    assert "other" in CONTEST_REASON_CODES
    assert all(len(code) <= 64 for code in CONTEST_REASON_CODES)
