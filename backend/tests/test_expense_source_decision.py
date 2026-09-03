from datetime import datetime, timedelta

from app.services.expense_source_decision import (
    DECISION_DEADLINE_DAYS,
    ExpenseSourceDecisionState,
    ExpenseSourceMode,
    resolve_expense_source_mode,
)

STARTED = datetime(2026, 1, 1)


def test_explicit_manual_decision_wins_immediately():
    state = ExpenseSourceDecisionState(
        onboarding_started_at=STARTED, decision=ExpenseSourceMode.MANUAL_ONLY, decided_at=STARTED
    )
    resolved = resolve_expense_source_mode(state, evaluated_at=STARTED + timedelta(days=1))
    assert resolved.mode == ExpenseSourceMode.MANUAL_ONLY
    assert resolved.is_explicit_decision is True
    assert resolved.resolved_at == STARTED


def test_explicit_statement_parsing_decision_wins_before_deadline():
    state = ExpenseSourceDecisionState(
        onboarding_started_at=STARTED,
        decision=ExpenseSourceMode.STATEMENT_PARSING_ENABLED,
        decided_at=STARTED + timedelta(days=2),
    )
    resolved = resolve_expense_source_mode(state, evaluated_at=STARTED + timedelta(days=3))
    assert resolved.mode == ExpenseSourceMode.STATEMENT_PARSING_ENABLED
    assert resolved.is_explicit_decision is True


def test_explicit_decision_still_wins_after_deadline():
    # An explicit choice, once made, isn't overridden just because the
    # 14-day default-resolution window has since passed.
    state = ExpenseSourceDecisionState(
        onboarding_started_at=STARTED,
        decision=ExpenseSourceMode.STATEMENT_PARSING_ENABLED,
        decided_at=STARTED + timedelta(days=1),
    )
    resolved = resolve_expense_source_mode(state, evaluated_at=STARTED + timedelta(days=100))
    assert resolved.mode == ExpenseSourceMode.STATEMENT_PARSING_ENABLED
    assert resolved.is_explicit_decision is True


def test_no_decision_before_deadline_is_manual_but_not_explicit():
    state = ExpenseSourceDecisionState(onboarding_started_at=STARTED, decision=None)
    resolved = resolve_expense_source_mode(state, evaluated_at=STARTED + timedelta(days=5))
    assert resolved.mode == ExpenseSourceMode.MANUAL_ONLY
    assert resolved.is_explicit_decision is False
    assert resolved.resolved_at is None


def test_no_decision_at_exact_deadline_auto_resolves_to_manual():
    # Auto-resolution is a default taking effect, not a human decision —
    # is_explicit_decision stays False, but resolved_at is now set (no
    # longer None), which is how a caller tells "defaulted" apart from
    # "still pending" even though both report the same manual_only mode.
    state = ExpenseSourceDecisionState(onboarding_started_at=STARTED, decision=None)
    deadline = STARTED + timedelta(days=DECISION_DEADLINE_DAYS)
    resolved = resolve_expense_source_mode(state, evaluated_at=deadline)
    assert resolved.mode == ExpenseSourceMode.MANUAL_ONLY
    assert resolved.is_explicit_decision is False
    assert resolved.resolved_at == deadline


def test_no_decision_long_after_deadline_auto_resolves_to_manual():
    state = ExpenseSourceDecisionState(onboarding_started_at=STARTED, decision=None)
    resolved = resolve_expense_source_mode(state, evaluated_at=STARTED + timedelta(days=90))
    assert resolved.mode == ExpenseSourceMode.MANUAL_ONLY
    assert resolved.is_explicit_decision is False
    assert resolved.resolved_at is not None


def test_custom_deadline_is_respected():
    state = ExpenseSourceDecisionState(onboarding_started_at=STARTED, decision=None)
    resolved = resolve_expense_source_mode(state, evaluated_at=STARTED + timedelta(days=8), deadline_days=7)
    assert resolved.is_explicit_decision is False
    assert resolved.resolved_at is not None
    assert resolved.mode == ExpenseSourceMode.MANUAL_ONLY
