import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.models.suggestion_event import SuggestionEvent
from app.services.financial_position import ExpenseFrequency
from app.services.onboarding import ProfileNotFoundError, add_emi, add_expense_item, upsert_profile
from app.services.debt_leak_service import compute_and_log_debt_leak_report

USER = "debtleak-user-1"


def _make_profile(session, **overrides):
    defaults = dict(
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=500_000_00,
    )
    defaults.update(overrides)
    return upsert_profile(session, **defaults)


def test_requires_existing_profile(session):
    with pytest.raises(ProfileNotFoundError):
        compute_and_log_debt_leak_report(session, "nobody")


def test_no_debts_no_surplus_still_returns_leak_only_report(session):
    _make_profile(session, income_paise=50_000_00, cash_balance_paise=100_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=45_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)

    report = compute_and_log_debt_leak_report(session, USER)
    assert report.avalanche_snowball is None
    assert report.prepay_vs_invest is None
    assert report.leak is not None
    assert report.expense_source_mode == "manual_only"
    assert report.expense_source_is_explicit is False


def test_debts_with_positive_surplus_populates_avalanche_snowball_and_prepay(session):
    _make_profile(session, income_paise=100_000_00, cash_balance_paise=500_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_emi(session, user_id=USER, lender="High Rate Loan Co", amount_paise=15_000_00, remaining_tenure_months=36, annual_rate_bps=1800)
    add_emi(session, user_id=USER, lender="Low Rate Loan Co", amount_paise=5_000_00, remaining_tenure_months=24, annual_rate_bps=800)

    report = compute_and_log_debt_leak_report(session, USER)

    assert report.avalanche_snowball is not None
    assert report.avalanche_snowball.avalanche.converged is True
    assert report.prepay_vs_invest is not None
    assert report.prepay_vs_invest.guaranteed_annual_rate_pct == 18  # highest-rate debt targeted


def test_debts_with_zero_surplus_leaves_avalanche_snowball_none(session):
    _make_profile(session, income_paise=30_000_00, cash_balance_paise=100_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=25_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_emi(session, user_id=USER, lender="Loan Co", amount_paise=10_000_00, remaining_tenure_months=24, annual_rate_bps=1200)
    # income 30,000 - rent 25,000 - EMI 10,000 = negative surplus

    report = compute_and_log_debt_leak_report(session, USER)
    assert report.avalanche_snowball is None
    assert report.prepay_vs_invest is None


def test_leak_report_flows_through_into_headline(session):
    _make_profile(session, income_paise=100_000_00, cash_balance_paise=800_000_00)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=30_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_expense_item(session, user_id=USER, category="Streaming service", amount_paise=649_00, frequency=ExpenseFrequency.MONTHLY, is_essential=False)
    add_expense_item(session, user_id=USER, category="Bank account maintenance charge", amount_paise=200_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)

    report = compute_and_log_debt_leak_report(session, USER)

    assert report.total_recoverable_annual_paise > 0
    assert report.total_recoverable_annual_paise == report.leak.total_recoverable_annual_paise
    labels = {c.label for c in report.leak.components}
    assert any("Idle cash" in label for label in labels)
    assert any("Rent" not in label and "fee" in label.lower() for label in labels)


def test_logs_exactly_one_debt_leak_engine_suggestion_event(session):
    _make_profile(session)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)

    compute_and_log_debt_leak_report(session, USER)

    events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="debt_leak_engine").all()
    assert len(events) == 1
    event = events[0]
    assert "total_recoverable_annual_paise" in event.suggested_value
    assert "leak_components" in event.suggested_value
    assert "data_source_note" in event.suggested_value
    assert event.market_context["expense_source_mode"] == "manual_only"


def test_recomputing_updates_the_same_snapshot_but_logs_a_new_event(session):
    _make_profile(session)
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)

    compute_and_log_debt_leak_report(session, USER)
    compute_and_log_debt_leak_report(session, USER)

    events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="debt_leak_engine").all()
    assert len(events) == 2  # each computation is its own logged event, unlike the upserted snapshot
