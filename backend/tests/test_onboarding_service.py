from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.onboarding import EmploymentType, IncomeStability, InsuranceType
from app.models.user_monthly_snapshot import UserMonthlySnapshot
from app.services.expense_source_decision import ExpenseSourceMode
from app.services.financial_position import ExpenseFrequency
from app.services.onboarding import (
    ProfileNotFoundError,
    add_emi,
    add_expense_item,
    add_holding,
    add_insurance_policy,
    complete_onboarding,
    compute_financial_position,
    get_expense_source_mode,
    record_expense_source_decision,
    upsert_profile,
)

USER = "onboard-user-1"


def _make_profile(session, **overrides):
    defaults = dict(
        user_id=USER,
        income_paise=80_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=1,
        cash_balance_paise=200_000_00,
    )
    defaults.update(overrides)
    return upsert_profile(session, **defaults)


def test_upsert_profile_creates_and_updates(session):
    profile = _make_profile(session)
    assert profile.user_id == USER
    assert profile.onboarding_started_at is not None
    assert profile.onboarding_completed_at is None

    updated = upsert_profile(
        session,
        user_id=USER,
        income_paise=90_000_00,
        income_stability=IncomeStability.IRREGULAR,
        employment_type=EmploymentType.FREELANCER,
        dependents_count=2,
        cash_balance_paise=250_000_00,
    )
    assert updated.income_paise == 90_000_00
    assert updated.income_stability == IncomeStability.IRREGULAR
    # started_at must not reset on update
    assert updated.onboarding_started_at == profile.onboarding_started_at


def test_add_emi_expense_holding_require_existing_profile(session):
    with pytest.raises(ProfileNotFoundError):
        add_emi(session, user_id="nobody", lender="X Bank", amount_paise=1000, remaining_tenure_months=12, annual_rate_bps=1000)
    with pytest.raises(ProfileNotFoundError):
        add_expense_item(session, user_id="nobody", category="rent", amount_paise=1000, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    with pytest.raises(ProfileNotFoundError):
        add_holding(session, user_id="nobody", description="Mutual fund", value_paise=1000)


def test_full_onboarding_end_to_end_and_hand_checked_metrics(session):
    _make_profile(session, income_paise=80_000_00, cash_balance_paise=200_000_00)

    add_emi(session, user_id=USER, lender="HDFC Home Loan", amount_paise=25_000_00, remaining_tenure_months=240, annual_rate_bps=850)
    add_holding(session, user_id=USER, description="Mutual funds", value_paise=150_000_00)
    add_holding(session, user_id=USER, description="Fixed deposit", value_paise=50_000_00)
    add_expense_item(session, user_id=USER, category="rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_expense_item(session, user_id=USER, category="groceries", amount_paise=8_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_expense_item(session, user_id=USER, category="dining_out", amount_paise=5_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=False)
    add_expense_item(session, user_id=USER, category="insurance_premium", amount_paise=24_000_00, frequency=ExpenseFrequency.ANNUAL, is_essential=True)
    add_insurance_policy(session, user_id=USER, policy_type=InsuranceType.LIFE, sum_assured_paise=50_00_000_00)

    position = compute_financial_position(session, USER)
    # same hand-checked scenario as test_financial_position.py
    assert position["net_worth_paise"] == -248_077_100
    assert position["monthly_surplus_paise"] == 20_000_00
    assert position["buffer_coverage_months"] == Decimal("6.67")
    assert position["emi_to_income_ratio"] == Decimal("0.3125")

    profile, snapshot = complete_onboarding(session, USER, completed_at=datetime(2026, 9, 3, tzinfo=timezone.utc))

    assert profile.onboarding_completed_at is not None
    assert snapshot.user_id == USER
    assert snapshot.month == date(2026, 9, 1)
    assert snapshot.income == 80_000_00
    assert snapshot.surplus == 20_000_00
    assert snapshot.cash == 200_000_00
    assert snapshot.debt_to_income_ratio == Decimal("0.3125")
    assert snapshot.buffer_coverage_months == Decimal("6.67")

    # exactly one snapshot row exists for this user/month
    rows = session.query(UserMonthlySnapshot).filter_by(user_id=USER).all()
    assert len(rows) == 1


def test_material_edit_after_completion_rewrites_same_month_snapshot(session):
    _make_profile(session, income_paise=50_000_00, cash_balance_paise=100_000_00)
    add_expense_item(session, user_id=USER, category="rent", amount_paise=10_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    _, first_snapshot = complete_onboarding(session, USER, completed_at=datetime(2026, 9, 3, tzinfo=timezone.utc))
    assert first_snapshot.surplus == 40_000_00

    # a material edit (new EMI) after completion should update the same
    # month's row, not create a second one
    add_emi(session, user_id=USER, lender="Bike Loan Co", amount_paise=5_000_00, remaining_tenure_months=12, annual_rate_bps=1000)

    rows = session.query(UserMonthlySnapshot).filter_by(user_id=USER).all()
    assert len(rows) == 1
    assert rows[0].surplus == 35_000_00  # 50,000 - 10,000 - 5,000


def test_insurance_policy_is_not_a_material_edit(session):
    _make_profile(session, income_paise=50_000_00, cash_balance_paise=100_000_00)
    add_expense_item(session, user_id=USER, category="rent", amount_paise=10_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    complete_onboarding(session, USER, completed_at=datetime(2026, 9, 3, tzinfo=timezone.utc))

    rows_before = session.query(UserMonthlySnapshot).filter_by(user_id=USER).all()
    add_insurance_policy(session, user_id=USER, policy_type=InsuranceType.HEALTH, sum_assured_paise=10_00_000_00)
    rows_after = session.query(UserMonthlySnapshot).filter_by(user_id=USER).all()

    assert len(rows_before) == len(rows_after) == 1
    assert rows_before[0].computed_at == rows_after[0].computed_at


def test_expense_source_decision_defaults_to_manual_and_can_be_recorded(session):
    _make_profile(session)
    resolved = get_expense_source_mode(session, USER, evaluated_at=datetime.now(timezone.utc))
    assert resolved.mode == ExpenseSourceMode.MANUAL_ONLY
    assert resolved.is_explicit_decision is False

    record_expense_source_decision(session, user_id=USER, decision=ExpenseSourceMode.STATEMENT_PARSING_ENABLED)
    resolved_after = get_expense_source_mode(session, USER, evaluated_at=datetime.now(timezone.utc))
    assert resolved_after.mode == ExpenseSourceMode.STATEMENT_PARSING_ENABLED
    assert resolved_after.is_explicit_decision is True
