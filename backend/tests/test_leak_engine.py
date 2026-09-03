from decimal import Decimal

from app.services.financial_position import ExpenseFrequency
from app.services.leak_engine import (
    ExpenseItemInput,
    build_leak_report,
    compute_idle_cash,
    detect_fee_drag,
    detect_recurring_charge_candidates,
    is_subscription_like,
)

MONTHLY = ExpenseFrequency.MONTHLY
ANNUAL = ExpenseFrequency.ANNUAL
ONE_TIME = ExpenseFrequency.ONE_TIME


# --- idle cash ---


def test_idle_cash_above_buffer_hand_checked():
    # essential expense Rs 50,000/mo -> required buffer = 6 * 50,000 = Rs 3,00,000
    # cash Rs 5,00,000 -> idle = Rs 2,00,000 -> opportunity cost @ 6.50% = Rs 13,000/yr
    result = compute_idle_cash(cash_balance_paise=500_000_00, essential_monthly_expense_paise=50_000_00)
    assert result.required_buffer_paise == 300_000_00
    assert result.idle_cash_paise == 200_000_00
    assert result.reference_rate_annual_pct == Decimal("6.50")
    assert result.opportunity_cost_annual_paise == 13_000_00


def test_idle_cash_below_buffer_is_zero_not_negative():
    result = compute_idle_cash(cash_balance_paise=100_000_00, essential_monthly_expense_paise=50_000_00)
    assert result.idle_cash_paise == 0
    assert result.opportunity_cost_annual_paise == 0


def test_idle_cash_exactly_at_buffer_is_zero():
    result = compute_idle_cash(cash_balance_paise=300_000_00, essential_monthly_expense_paise=50_000_00)
    assert result.idle_cash_paise == 0


# --- fee drag ---


def test_fee_drag_matches_and_annualizes_hand_checked():
    expenses = [
        ExpenseItemInput("e1", "Bank account maintenance charge", 200_00, MONTHLY, True),
        ExpenseItemInput("e2", "AMC for demat account", 500_00, ANNUAL, True),
        ExpenseItemInput("e3", "Groceries", 8_000_00, MONTHLY, True),
    ]
    result = detect_fee_drag(expenses)
    matched_ids = {i.item_id for i in result.items}
    assert matched_ids == {"e1", "e2"}
    assert result.total_annual_paise == 2_400_00 + 500_00  # 200*12 + 500


def test_fee_drag_ignores_one_time_items():
    expenses = [ExpenseItemInput("e1", "One-time bank penalty", 500_00, ONE_TIME, True)]
    result = detect_fee_drag(expenses)
    assert result.items == ()
    assert result.total_annual_paise == 0


def test_fee_drag_no_matches_is_empty():
    expenses = [ExpenseItemInput("e1", "Groceries", 8_000_00, MONTHLY, True)]
    result = detect_fee_drag(expenses)
    assert result.items == ()


# --- recurring charge candidates ---


def test_subscription_keyword_flags_discretionary_recurring_item():
    expenses = [ExpenseItemInput("e1", "Streaming service", 649_00, MONTHLY, False)]
    result = detect_recurring_charge_candidates(expenses)
    assert len(result) == 1
    assert result[0].item_id == "e1"
    assert any(r.startswith("subscription_keyword:") for r in result[0].reasons)
    assert result[0].annual_amount_paise == 649_00 * 12


def test_subscription_keyword_does_not_flag_essential_item():
    # same wording, but the user marked it essential -- respect that
    expenses = [ExpenseItemInput("e1", "Streaming service", 649_00, MONTHLY, True)]
    result = detect_recurring_charge_candidates(expenses)
    assert result == []


def test_near_duplicate_categories_flag_each_other():
    expenses = [
        ExpenseItemInput("e1", "Gym membership", 1_500_00, MONTHLY, False),
        ExpenseItemInput("e2", "Gym membership fee", 1_500_00, MONTHLY, False),
        ExpenseItemInput("e3", "Groceries", 8_000_00, MONTHLY, True),
    ]
    result = detect_recurring_charge_candidates(expenses)
    by_id = {c.item_id: c for c in result}
    assert "e1" in by_id and "e2" in by_id
    assert "e3" not in by_id
    assert any(r.startswith("possible_duplicate_of:e2") for r in by_id["e1"].reasons)
    assert any(r.startswith("possible_duplicate_of:e1") for r in by_id["e2"].reasons)


def test_unrelated_categories_are_not_flagged_as_duplicates():
    expenses = [
        ExpenseItemInput("e1", "Rent", 20_000_00, MONTHLY, True),
        ExpenseItemInput("e2", "Electricity bill", 2_000_00, MONTHLY, True),
    ]
    result = detect_recurring_charge_candidates(expenses)
    assert result == []


def test_one_time_items_are_never_recurring_candidates():
    expenses = [ExpenseItemInput("e1", "Streaming service", 649_00, ONE_TIME, False)]
    result = detect_recurring_charge_candidates(expenses)
    assert result == []


# --- combined leak report ---


def test_build_leak_report_sums_all_component_types_hand_checked():
    expenses = [
        ExpenseItemInput("fee1", "Bank account maintenance charge", 200_00, MONTHLY, True),  # 2,400_00/yr fee
        ExpenseItemInput("sub1", "Streaming service", 649_00, MONTHLY, False),  # 7,788_00/yr subscription
        ExpenseItemInput("essential1", "Rent", 20_000_00, MONTHLY, True),  # not a leak
    ]
    report = build_leak_report(cash_balance_paise=500_000_00, essential_monthly_expense_paise=50_000_00, expenses=expenses)

    assert report.idle_cash.opportunity_cost_annual_paise == 13_000_00
    assert report.fee_drag.total_annual_paise == 2_400_00
    assert len(report.recurring_candidates) == 1

    component_ids = {c.component_id for c in report.components}
    assert "idle_cash" in component_ids
    assert "fee_drag:fee1" in component_ids
    assert "recurring:sub1" in component_ids

    expected_total = 13_000_00 + 2_400_00 + (649_00 * 12)
    assert report.total_recoverable_annual_paise == expected_total

    for component in report.components:
        assert component.explanation
        assert component.concrete_action


def test_build_leak_report_every_component_has_explanation_and_action():
    expenses = [
        ExpenseItemInput("fee1", "ATM fee", 100_00, MONTHLY, True),
        ExpenseItemInput("sub1", "Gym membership", 1_500_00, MONTHLY, False),
    ]
    report = build_leak_report(cash_balance_paise=100_000_00, essential_monthly_expense_paise=50_000_00, expenses=expenses)
    assert len(report.components) >= 2
    for c in report.components:
        assert isinstance(c.annual_amount_paise, int) and c.annual_amount_paise > 0
        assert len(c.explanation) > 0
        assert len(c.concrete_action) > 0


def test_leak_report_carries_the_manual_entry_scope_note():
    report = build_leak_report(cash_balance_paise=0, essential_monthly_expense_paise=10_000_00, expenses=[])
    assert "manually entered" in report.data_source_note
    assert "statement parser" in report.data_source_note


def test_empty_inputs_produce_zero_recoverable_without_crashing():
    report = build_leak_report(cash_balance_paise=0, essential_monthly_expense_paise=0, expenses=[])
    assert report.total_recoverable_annual_paise == 0
    assert report.components == ()


def test_is_subscription_like_matches_keyword_and_rejects_non_matches():
    assert is_subscription_like("Streaming service") is True
    assert is_subscription_like("Gym membership") is True
    assert is_subscription_like("Rent") is False
    assert is_subscription_like("Groceries") is False
