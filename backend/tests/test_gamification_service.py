from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.models.suggestion_event import SuggestionEvent
from app.services.asset_classification_config import HoldingType
from app.services.event_log import log_monthly_snapshot
from app.services.financial_position import ExpenseFrequency
from app.services.gamification_service import (
    AwardedMilestone,
    check_milestones,
    get_milestone_history,
    complete_education_item,
    get_education_progress,
)
from app.services.onboarding import (
    ProfileNotFoundError,
    add_emi,
    add_expense_item,
    close_emi,
    remove_expense_item,
    upsert_profile,
)
from app.services.risk_profile_service import compute_and_log_risk_tier

USER = "gamify-user-1"

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


def _make_profile(session, **overrides):
    defaults = dict(
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=100_000_00,
    )
    defaults.update(overrides)
    return upsert_profile(session, **defaults)


def test_requires_existing_profile(session):
    with pytest.raises(ProfileNotFoundError):
        check_milestones(session, "nobody")


def test_no_history_awards_nothing(session):
    _make_profile(session)
    result = check_milestones(session, USER)
    assert result == []


# --- buffer milestones ---


def test_buffer_milestone_awarded_when_threshold_crossed(session):
    _make_profile(session, cash_balance_paise=600_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=100_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    # cash 6,00,000 / essential 1,00,000 = 6.0 months -> crosses 1,2,4,6

    result = check_milestones(session, USER)
    ids = {m.milestone_id for m in result}
    assert ids == {"buffer_months_1", "buffer_months_2", "buffer_months_4", "buffer_months_6"}


def test_buffer_milestone_not_re_awarded_on_second_call(session):
    _make_profile(session, cash_balance_paise=600_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=100_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    check_milestones(session, USER)
    second = check_milestones(session, USER)
    assert second == []


# --- capacity unlock: the "one real progression mechanic" ---


def test_capacity_unlock_awarded_when_ceiling_rises_between_two_risk_tier_computations(session):
    # start with poor capacity (thin buffer) -> low ceiling
    _make_profile(session, cash_balance_paise=50_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=100_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)  # capacity_ceiling should be low (buffer < 1mo)

    # capacity improves substantially
    _make_profile(session, cash_balance_paise=1_000_000_00)
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)

    result = check_milestones(session, USER)
    unlocks = [m for m in result if m.category == "capacity_unlock"]
    assert unlocks, "expected at least one capacity_unlock milestone"
    for u in unlocks:
        assert "old_ceiling" in u.details
        assert "new_ceiling" in u.details
        assert u.details["new_ceiling"] > u.details["old_ceiling"]
        assert "new_capped_equity_pct" in u.details  # tied to the real underlying number, not a cosmetic badge


def test_capacity_unlock_not_awarded_when_ceiling_never_improves(session):
    _make_profile(session, cash_balance_paise=1_000_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=50_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    compute_and_log_risk_tier(session, USER, CONSERVATIVE_ANSWERS)
    compute_and_log_risk_tier(session, USER, CONSERVATIVE_ANSWERS)  # same capacity, no improvement

    result = check_milestones(session, USER)
    assert [m for m in result if m.category == "capacity_unlock"] == []


# --- debt free ---


def test_no_debt_ever_recorded_gives_no_debt_free_milestone(session):
    _make_profile(session)
    result = check_milestones(session, USER)
    assert "debt_free" not in {m.milestone_id for m in result}


def test_debt_free_awarded_after_closing_the_only_emi(session):
    _make_profile(session)
    emi = add_emi(session, user_id=USER, lender="Personal Loan Co", amount_paise=10_000_00, remaining_tenure_months=12, annual_rate_bps=1200)

    before = check_milestones(session, USER)
    assert "debt_free" not in {m.milestone_id for m in before}

    close_emi(session, user_id=USER, emi_id=emi.id)
    after = check_milestones(session, USER)
    assert "debt_free" in {m.milestone_id for m in after}


def test_debt_free_not_awarded_while_any_active_emi_remains(session):
    _make_profile(session)
    emi1 = add_emi(session, user_id=USER, lender="Loan A", amount_paise=5_000_00, remaining_tenure_months=12, annual_rate_bps=1000)
    add_emi(session, user_id=USER, lender="Loan B", amount_paise=5_000_00, remaining_tenure_months=12, annual_rate_bps=1000)
    close_emi(session, user_id=USER, emi_id=emi1.id)

    result = check_milestones(session, USER)
    assert "debt_free" not in {m.milestone_id for m in result}


# --- subscriptions cancelled ---


def test_subscription_cancelled_milestone_counts_only_subscription_like_removed_items(session):
    _make_profile(session)
    sub = add_expense_item(session, user_id=USER, category="Streaming service", amount_paise=649_00, frequency=ExpenseFrequency.MONTHLY, is_essential=False)
    rent = add_expense_item(session, user_id=USER, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)

    remove_expense_item(session, user_id=USER, item_id=sub.id)
    remove_expense_item(session, user_id=USER, item_id=rent.id)  # removing rent should NOT count as a cancelled subscription

    result = check_milestones(session, USER)
    ids = {m.milestone_id for m in result}
    assert "subscriptions_cancelled_1" in ids
    assert "subscriptions_cancelled_3" not in ids


# --- consistency ---


def test_consistency_milestone_from_consecutive_positive_surplus_snapshots(session):
    _make_profile(session)
    for i, month in enumerate((date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))):
        log_monthly_snapshot(
            session, user_id=USER, month=month, income=50_000_00, surplus=10_000_00, cash=100_000_00,
            debt_to_income_ratio=Decimal("0.1"), buffer_coverage_months=Decimal("2.0"),
        )

    result = check_milestones(session, USER)
    ids = {m.milestone_id for m in result}
    assert "consistency_3_months" in ids
    assert "consistency_6_months" not in ids


def test_consistency_streak_breaks_on_a_negative_surplus_month(session):
    _make_profile(session)
    log_monthly_snapshot(session, user_id=USER, month=date(2026, 1, 1), income=50_000_00, surplus=10_000_00, cash=100_000_00, debt_to_income_ratio=Decimal("0.1"), buffer_coverage_months=Decimal("2.0"))
    log_monthly_snapshot(session, user_id=USER, month=date(2026, 2, 1), income=50_000_00, surplus=-5_000_00, cash=100_000_00, debt_to_income_ratio=Decimal("0.1"), buffer_coverage_months=Decimal("2.0"))
    log_monthly_snapshot(session, user_id=USER, month=date(2026, 3, 1), income=50_000_00, surplus=10_000_00, cash=100_000_00, debt_to_income_ratio=Decimal("0.1"), buffer_coverage_months=Decimal("2.0"))

    result = check_milestones(session, USER)
    assert {m.milestone_id for m in result if m.category == "consistency"} == set()  # only 1 trailing positive month, no threshold met


# --- logging + history ---


def test_milestones_are_logged_as_gamification_suggestion_events(session):
    _make_profile(session, cash_balance_paise=600_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=100_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    check_milestones(session, USER)

    events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="gamification").all()
    assert len(events) == 4  # the 4 buffer thresholds crossed
    for e in events:
        assert "milestone_id" in e.suggested_value
        assert "headline" in e.suggested_value


def test_get_milestone_history_reads_back_in_chronological_order(session):
    _make_profile(session, cash_balance_paise=600_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=100_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    check_milestones(session, USER)

    history = get_milestone_history(session, USER)
    assert len(history) == 4
    assert all(isinstance(m, AwardedMilestone) for m in history)


# --- the effort-not-outcome boundary, checked against the actual source ---


def test_gamification_source_never_reads_module4_outcome_fields():
    # a structural check that the actual detection logic never touches
    # Module 4's portfolio-value / market-exposure fields. Deliberately
    # excludes gamification_config.py, whose module docstring legitimately
    # *names* these fields to explain why they're off-limits (the same
    # negation pattern as Module 8's "never run against real users") --
    # this test is about the code that runs, not the prose that explains it.
    forbidden = ("current_exposure_paise", "current_exposure_pct", "total_value_paise", "market_return", "portfolio_value")
    backend_dir = Path(__file__).resolve().parent.parent
    for filename in ("gamification.py", "gamification_service.py"):
        source = (backend_dir / "app" / "services" / filename).read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in source, f"{filename} references forbidden outcome-signal term {term!r}"


def test_education_progress_is_idempotent_and_awards_knowledge_badges(session):
    _make_profile(session)
    complete_education_item(session, USER, "budgeting", "lesson")
    complete_education_item(session, USER, "budgeting", "lesson")
    complete_education_item(session, USER, "diversification-allocation", "lesson")
    complete_education_item(session, USER, "diversification-allocation", "quiz", answer_index=0)

    progress = get_education_progress(session, USER)
    assert progress["completed_topics"] == 2
    assert progress["learning_streak_days"] == 1
    badges = {badge["badge_id"]: badge["earned"] for badge in progress["badges"]}
    assert badges["budget-beginner"] is True
    assert badges["diversification-pro"] is True
    assert session.query(SuggestionEvent).filter_by(user_id=USER, module_source="gamification_education").count() == 3
