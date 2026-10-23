import pytest

from app.models.onboarding import EmploymentType, IncomeStability, InsuranceType
from app.models.suggestion_event import SuggestionEvent
from app.services.financial_position import ExpenseFrequency
from app.services.onboarding import add_emi, add_expense_item, add_insurance_policy, upsert_profile
from app.services.risk_profile_ml import FEATURE_ORDER_REDUCED, MODEL_VERSION_REDUCED
from app.services.risk_profile_service import ProfileNotFoundError, compute_and_log_risk_tier

USER = "risk-user-1"

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
}

# Just the 4 "main" quick-mode questions, from AGGRESSIVE_ANSWERS.
AGGRESSIVE_ANSWERS_QUICK = {qid: AGGRESSIVE_ANSWERS[qid] for qid in FEATURE_ORDER_REDUCED}


def test_compute_and_log_risk_tier_requires_existing_profile(session):
    with pytest.raises(ProfileNotFoundError):
        compute_and_log_risk_tier(session, "nobody", AGGRESSIVE_ANSWERS)


def _setup_core_scenario(session):
    """Module 2 onboarding state that hand-computes to a 2-month buffer and
    a 45% EMI-to-income ratio, on Rs 1,00,000/month income -- the exact
    core product scenario, built through the real onboarding service
    rather than constructed CapacityInputs directly."""
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=200_000_00,
    )
    add_expense_item(
        session, user_id=USER, category="essentials", amount_paise=100_000_00,
        frequency=ExpenseFrequency.MONTHLY, is_essential=True,
    )
    add_emi(
        session, user_id=USER, lender="Heavy Personal Loan Co", amount_paise=45_000_00,
        remaining_tenure_months=24, annual_rate_bps=1200,
    )


def test_core_scenario_end_to_end_caps_the_tier(session):
    _setup_core_scenario(session)

    result = compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)

    assert result.stated_tier == 5  # "aggressive" questionnaire answers
    assert result.capacity_ceiling == 2  # heavy EMI is the binding constraint
    assert result.final_tier == 2
    assert result.capped is True
    assert result.binding_constraints == ("emi_to_income_ratio",)
    assert "buffer_months" not in result.binding_constraints

    unlock = result.unlock_conditions[0]
    assert "Rs 25,000" in unlock.message
    assert "20%" in unlock.message


def test_core_scenario_logs_a_suggestion_event_with_binding_constraint(session):
    _setup_core_scenario(session)
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)

    events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="risk_profile").all()
    assert len(events) == 1
    event = events[0]

    assert event.tier == "2"  # final tier
    assert event.suggested_value["stated_tier"] == 5
    assert event.suggested_value["capacity_ceiling"] == 2
    assert event.suggested_value["final_tier"] == 2
    assert event.suggested_value["capped"] is True
    assert event.suggested_value["binding_constraints"] == ["emi_to_income_ratio"]
    assert len(event.suggested_value["unlock_conditions"]) == 1
    assert event.suggested_value["unlock_conditions"][0]["constraint"] == "emi_to_income_ratio"
    assert event.suggested_value["answers"] == AGGRESSIVE_ANSWERS

    assert event.market_context["buffer_coverage_months"] == "2.00"
    assert event.market_context["emi_to_income_ratio"] == "0.4500"
    assert event.market_context["income_stability"] == "regular"

    # action_taken/chosen_value are untouched at computation time -- a
    # tiering result isn't something a user accepts/rejects the way a
    # dollar-figure suggestion is
    assert event.action_taken is None
    assert event.chosen_value is None


def test_uncapped_scenario_logs_capped_false_and_no_binding_constraints(session):
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=1_000_000_00,
    )
    add_expense_item(
        session, user_id=USER, category="essentials", amount_paise=50_000_00,
        frequency=ExpenseFrequency.MONTHLY, is_essential=True,
    )

    result = compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)
    assert result.capped is False
    assert result.final_tier == 5

    event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="risk_profile").one()
    assert event.suggested_value["capped"] is False
    assert event.suggested_value["binding_constraints"] == []


def test_insurance_adequacy_feeds_from_module2_life_policies(session):
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=2,
        cash_balance_paise=1_000_000_00,
    )
    add_expense_item(
        session, user_id=USER, category="essentials", amount_paise=50_000_00,
        frequency=ExpenseFrequency.MONTHLY, is_essential=True,
    )
    add_insurance_policy(session, user_id=USER, policy_type=InsuranceType.LIFE, sum_assured_paise=50_00_000_00)
    add_insurance_policy(session, user_id=USER, policy_type=InsuranceType.HEALTH, sum_assured_paise=10_00_000_00)

    result = compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)

    # required cover = 100,000_00 * 12 * 10 = 1,20,00,000_00; life cover
    # counted is only the LIFE policy (50,00,000_00), health is excluded
    assert result.capped is True
    assert result.binding_constraints == ("insurance_adequacy",)


# --- quick mode (4 of 7 answers, ML-estimated stated tier) -----------------


def test_quick_mode_with_exactly_the_4_required_answers_succeeds(session):
    _setup_core_scenario(session)

    result = compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS_QUICK)

    assert result.estimation_method == MODEL_VERSION_REDUCED
    assert 1 <= result.stated_tier <= 5
    # same capacity ceiling as the full-answers version of this scenario
    # (capacity never depends on the questionnaire) -- still caps the tier.
    assert result.capacity_ceiling == 2
    assert result.final_tier == min(result.stated_tier, 2)


def test_quick_mode_logs_risk_profile_ml_as_authoritative(session):
    _setup_core_scenario(session)
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS_QUICK)

    rule_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="risk_profile").one()
    assert rule_event.suggested_value["estimation_method"] == MODEL_VERSION_REDUCED
    assert rule_event.suggested_value["stated_score"] == 0  # no weighted-sum formula ran

    ml_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="risk_profile_ml").one()
    assert ml_event.suggested_value["is_authoritative"] is True
    assert ml_event.suggested_value["predicted_tier"] == rule_event.suggested_value["stated_tier"]


def test_six_of_seven_answers_is_rejected_not_silently_treated_as_quick_mode(session):
    _setup_core_scenario(session)
    incomplete = dict(AGGRESSIVE_ANSWERS)
    del incomplete["goal"]

    with pytest.raises(ValueError, match="goal"):
        compute_and_log_risk_tier(session, USER, incomplete)


def test_four_answers_that_are_not_the_required_set_is_rejected(session):
    _setup_core_scenario(session)
    # 4 answers, but not FEATURE_ORDER_REDUCED -- not a valid quick-mode
    # submission (the reduced model wasn't trained on these features).
    wrong_four = {
        "horizon": AGGRESSIVE_ANSWERS["horizon"],
        "drawdown_reaction": AGGRESSIVE_ANSWERS["drawdown_reaction"],
        "experience": AGGRESSIVE_ANSWERS["experience"],
        "goal": AGGRESSIVE_ANSWERS["goal"],
    }
    with pytest.raises(ValueError):
        compute_and_log_risk_tier(session, USER, wrong_four)


def test_full_seven_answers_still_uses_deterministic_scoring(session):
    _setup_core_scenario(session)
    result = compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)
    assert result.estimation_method == "deterministic"
    assert result.stated_tier == 5
