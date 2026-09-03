"""Module 6, leak half: pure, deterministic leak-detection logic. No I/O.

Scope note (see debt_leak_config.py for the full explanation): Module 2 is
manual-entry-only, so "recurring-charge detection via merchant-name
clustering and periodicity analysis" runs over already-declared recurring
ExpenseItem rows (category text + declared frequency), not a stream of
dated bank-statement transactions. `category` stands in for a merchant
name here — a real but reduced substitute.
"""

import difflib
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.services.debt_leak_config import (
    DUPLICATE_CATEGORY_SIMILARITY_THRESHOLD,
    FEE_KEYWORDS_V1,
    IDLE_CASH_BUFFER_TARGET_MONTHS,
    IDLE_CASH_REFERENCE_RATE_ANNUAL_BPS,
    SUBSCRIPTION_KEYWORDS_V1,
)
from app.services.financial_position import ExpenseFrequency

DATA_SOURCE_NOTE = (
    "Based only on manually entered recurring expense line items (Module 2 has no "
    "statement parser and none is planned without a fresh decision to build one — "
    "see expense_source_decision.py). Recurring-charge detection here matches "
    "declared category text against known patterns and against other declared "
    "categories for near-duplicates; it cannot see individual dated transactions "
    "or true merchant names the way a bank-statement feed would, so it will miss "
    "recurring charges the user hasn't entered as a distinct recurring expense."
)


@dataclass(frozen=True)
class ExpenseItemInput:
    item_id: str
    category: str
    amount_paise: int
    frequency: ExpenseFrequency
    is_essential: bool


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()


def is_subscription_like(category: str) -> bool:
    """Public wrapper over the same keyword match detect_recurring_charge_candidates
    uses, for callers (Module 10's "subscription cancelled" milestone) that
    just need a yes/no on one category string rather than the full
    candidate-detection pass."""
    text = _normalize(category)
    return any(keyword in text for keyword in SUBSCRIPTION_KEYWORDS_V1)


def _annual_equivalent_paise(amount_paise: int, frequency: ExpenseFrequency) -> int:
    if frequency == ExpenseFrequency.MONTHLY:
        return amount_paise * 12
    if frequency == ExpenseFrequency.ANNUAL:
        return amount_paise
    return 0  # ONE_TIME isn't a recurring drag


# --- recurring-charge candidates ---


@dataclass(frozen=True)
class RecurringChargeCandidate:
    item_id: str
    category: str
    annual_amount_paise: int
    reasons: tuple[str, ...]


def detect_recurring_charge_candidates(expenses: list[ExpenseItemInput]) -> list[RecurringChargeCandidate]:
    recurring = [e for e in expenses if e.frequency != ExpenseFrequency.ONE_TIME]
    normalized = {e.item_id: _normalize(e.category) for e in recurring}

    candidates: dict[str, list[str]] = {e.item_id: [] for e in recurring}

    # (a) subscription-style keyword match, discretionary items only --
    # essential-flagged items are the user's own judgment call, not ours
    for e in recurring:
        if e.is_essential:
            continue
        text = normalized[e.item_id]
        for keyword in SUBSCRIPTION_KEYWORDS_V1:
            if keyword in text:
                candidates[e.item_id].append(f"subscription_keyword:{keyword}")
                break

    # (b) near-duplicate category pairs, across ALL recurring items
    # regardless of essential flag -- this is a data-consolidation signal,
    # not a necessity judgment
    for i, a in enumerate(recurring):
        for b in recurring[i + 1 :]:
            ratio = difflib.SequenceMatcher(None, normalized[a.item_id], normalized[b.item_id]).ratio()
            if ratio >= DUPLICATE_CATEGORY_SIMILARITY_THRESHOLD:
                candidates[a.item_id].append(f"possible_duplicate_of:{b.item_id}")
                candidates[b.item_id].append(f"possible_duplicate_of:{a.item_id}")

    return [
        RecurringChargeCandidate(
            item_id=e.item_id,
            category=e.category,
            annual_amount_paise=_annual_equivalent_paise(e.amount_paise, e.frequency),
            reasons=tuple(candidates[e.item_id]),
        )
        for e in recurring
        if candidates[e.item_id]
    ]


# --- fee / drag audit ---


@dataclass(frozen=True)
class FeeDragItem:
    item_id: str
    category: str
    annual_amount_paise: int
    matched_keyword: str


@dataclass(frozen=True)
class FeeDragResult:
    items: tuple[FeeDragItem, ...]
    total_annual_paise: int


def detect_fee_drag(expenses: list[ExpenseItemInput]) -> FeeDragResult:
    items = []
    for e in expenses:
        if e.frequency == ExpenseFrequency.ONE_TIME:
            continue
        text = _normalize(e.category)
        matched = next((k for k in FEE_KEYWORDS_V1 if k in text), None)
        if matched:
            items.append(
                FeeDragItem(
                    item_id=e.item_id,
                    category=e.category,
                    annual_amount_paise=_annual_equivalent_paise(e.amount_paise, e.frequency),
                    matched_keyword=matched,
                )
            )
    return FeeDragResult(items=tuple(items), total_annual_paise=sum(i.annual_amount_paise for i in items))


# --- idle cash ---


@dataclass(frozen=True)
class IdleCashResult:
    required_buffer_paise: int
    idle_cash_paise: int
    reference_rate_annual_pct: Decimal
    opportunity_cost_annual_paise: int


def compute_idle_cash(cash_balance_paise: int, essential_monthly_expense_paise: int) -> IdleCashResult:
    required_buffer = int(
        (IDLE_CASH_BUFFER_TARGET_MONTHS * Decimal(essential_monthly_expense_paise)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    idle_cash = max(0, cash_balance_paise - required_buffer)
    rate = Decimal(IDLE_CASH_REFERENCE_RATE_ANNUAL_BPS) / 100
    opportunity_cost = int(
        (Decimal(idle_cash) * rate / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return IdleCashResult(
        required_buffer_paise=required_buffer,
        idle_cash_paise=idle_cash,
        reference_rate_annual_pct=rate.quantize(Decimal("0.01")),
        opportunity_cost_annual_paise=opportunity_cost,
    )


# --- combined headline ---


@dataclass(frozen=True)
class RecoverableComponent:
    component_id: str
    label: str
    annual_amount_paise: int
    explanation: str
    concrete_action: str


@dataclass(frozen=True)
class LeakReport:
    idle_cash: IdleCashResult
    fee_drag: FeeDragResult
    recurring_candidates: tuple[RecurringChargeCandidate, ...]
    components: tuple[RecoverableComponent, ...]
    total_recoverable_annual_paise: int
    data_source_note: str


def build_leak_report(
    cash_balance_paise: int, essential_monthly_expense_paise: int, expenses: list[ExpenseItemInput]
) -> LeakReport:
    idle_cash = compute_idle_cash(cash_balance_paise, essential_monthly_expense_paise)
    fee_drag = detect_fee_drag(expenses)
    recurring_candidates = detect_recurring_charge_candidates(expenses)

    components: list[RecoverableComponent] = []

    if idle_cash.opportunity_cost_annual_paise > 0:
        components.append(
            RecoverableComponent(
                component_id="idle_cash",
                label="Idle cash above your emergency buffer",
                annual_amount_paise=idle_cash.opportunity_cost_annual_paise,
                explanation=(
                    f"You hold cash above the {IDLE_CASH_BUFFER_TARGET_MONTHS}-month emergency buffer "
                    f"Module 2/3 use as adequate. At an illustrative {idle_cash.reference_rate_annual_pct}% "
                    "p.a. reference rate for a liquid, low-risk cash-equivalent instrument, that idle "
                    "amount is a real, quantifiable opportunity cost every year it sits uninvested."
                ),
                concrete_action=(
                    f"Move the amount above your buffer into a liquid, low-risk instrument instead of "
                    "letting it sit as idle cash."
                ),
            )
        )

    for item in fee_drag.items:
        components.append(
            RecoverableComponent(
                component_id=f"fee_drag:{item.item_id}",
                label=f"Recurring fee: {item.category}",
                annual_amount_paise=item.annual_amount_paise,
                explanation=f"This recurring expense item matched a known fee pattern ('{item.matched_keyword}').",
                concrete_action="Check whether this fee can be waived, negotiated down, or avoided (e.g. by meeting a minimum-balance or usage condition).",
            )
        )

    for candidate in recurring_candidates:
        components.append(
            RecoverableComponent(
                component_id=f"recurring:{candidate.item_id}",
                label=f"Recurring charge to review: {candidate.category}",
                annual_amount_paise=candidate.annual_amount_paise,
                explanation=f"Flagged as worth reviewing: {', '.join(candidate.reasons)}.",
                concrete_action="Confirm you still use this; cancel or consolidate it if not.",
            )
        )

    total = sum(c.annual_amount_paise for c in components)

    return LeakReport(
        idle_cash=idle_cash,
        fee_drag=fee_drag,
        recurring_candidates=tuple(recurring_candidates),
        components=tuple(components),
        total_recoverable_annual_paise=total,
        data_source_note=DATA_SOURCE_NOTE,
    )
