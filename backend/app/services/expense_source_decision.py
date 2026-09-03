"""Manual-vs-statement-parsing decision logic for expense entry.

This module builds manual line-item expense entry only. It deliberately
does NOT build a bank/card statement parser — but per the project brief,
that omission must be an explicit, recorded, dated decision point, not a
silent gap: whether a parser ever gets built determines whether leak
detection and idle-cash flagging are buildable later, so the choice (or
the absence of one) needs to be visible and traceable, not just implied by
what code happens to exist.

`resolve_expense_source_mode` is the pure decision-timeline logic (no I/O),
unit-tested on its own; the ORM-backed decision record lives in
app/models/onboarding.py and is persisted/read via app/services/onboarding.py.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

DECISION_DEADLINE_DAYS = 14


class ExpenseSourceMode(str, Enum):
    MANUAL_ONLY = "manual_only"
    STATEMENT_PARSING_ENABLED = "statement_parsing_enabled"


@dataclass(frozen=True)
class ExpenseSourceDecisionState:
    onboarding_started_at: datetime
    decision: ExpenseSourceMode | None = None
    decided_at: datetime | None = None


@dataclass(frozen=True)
class ResolvedExpenseSourceMode:
    mode: ExpenseSourceMode
    is_explicit_decision: bool  # False when this is the auto-applied default
    resolved_at: datetime | None  # when the decision (explicit or default) took effect


def resolve_expense_source_mode(
    state: ExpenseSourceDecisionState,
    evaluated_at: datetime,
    deadline_days: int = DECISION_DEADLINE_DAYS,
) -> ResolvedExpenseSourceMode:
    """An explicit decision, once made, always wins. Otherwise, once the
    deadline has elapsed with no decision made, the mode auto-resolves to
    manual-only — this is the "default to manual-entry-only if the decision
    isn't made within two weeks" rule made concrete and datable. Before the
    deadline, with no decision yet, the mode is still manual-only in
    practice (no parser exists to enable), but is reported as not-yet-
    explicit so a caller can tell "we chose this" apart from "nobody's
    decided yet."
    """
    if state.decision is not None:
        return ResolvedExpenseSourceMode(mode=state.decision, is_explicit_decision=True, resolved_at=state.decided_at)

    deadline = state.onboarding_started_at + timedelta(days=deadline_days)
    if evaluated_at >= deadline:
        return ResolvedExpenseSourceMode(mode=ExpenseSourceMode.MANUAL_ONLY, is_explicit_decision=False, resolved_at=deadline)

    return ResolvedExpenseSourceMode(mode=ExpenseSourceMode.MANUAL_ONLY, is_explicit_decision=False, resolved_at=None)
