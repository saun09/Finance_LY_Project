"""Module 9: transparency/rule-tracing layer. Reads exclusively from
Module 1's stored suggestion_event data (`suggested_value`,
`market_context`) — never recomputes a decision to explain it. If a
stored event is missing fields a decision type needs to fully reconstruct
its reasoning, that is reported as a gap (`gap_detected=True`,
`missing_fields`) rather than silently omitted or backfilled with a
freshly computed value, which would defeat the point of tracing what
*actually* drove the stored decision.

LABELING (per the module brief — read before touching FRAMING_LABEL or
any user-facing string here): every decision type built from Modules 3,
4, 6, and 7 is a weighted sum or a rule-table lookup, nothing more.
Printing the weights and the table lookup *is* the whole feature. These
are labeled "transparent reasoning" everywhere — never "explainable AI"
or "AI-powered," which would overclaim what a handful of `if` statements
and a dict lookup actually are. This module makes no model calls and
never will; see Module 1's original convention that scoring/cap logic
stays pure and deterministic, with no hidden state.

Module 5 (rumour verification) is out of scope for this file: it lives in
modules/rumour_verification/ as a standalone module with no runtime
dependency on this backend, and it produces its own trace at verification
time rather than through Module 1's event log. Its transparency view is
built in modules/rumour_verification/src/transparency.py instead, reusing
that trace directly (see that file's docstring for why "explanation" /
"explainable" language is appropriate there specifically, unlike here).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.suggestion_event import SuggestionEvent
from app.services.event_log import get_user_event_history

FRAMING_LABEL = "transparent reasoning"


@dataclass(frozen=True)
class DecisionTypeSpec:
    module_source: str
    display_name: str
    required_suggested_value_keys: tuple[str, ...]
    required_market_context_keys: tuple[str, ...]
    headline: Callable[[dict, dict], str]
    reasoning: Callable[[dict, dict], dict]


@dataclass(frozen=True)
class TraceResult:
    module_source: str
    display_name: str
    framing_label: str
    event_id: str
    timestamp: datetime
    headline: str
    reasoning: dict
    gap_detected: bool
    missing_fields: tuple[str, ...]


class NoSuchDecisionEventError(ValueError):
    pass


class UnknownDecisionTypeError(ValueError):
    pass


def _rupees(paise) -> str:
    try:
        return f"Rs {int(paise) / 100:,.0f}"
    except (TypeError, ValueError):
        return "Rs ?"


def _risk_profile_headline(v: dict, m: dict) -> str:
    tier_note = f"stated tier {v.get('stated_tier', '?')} -> final tier {v.get('final_tier', '?')}"
    if v.get("capped"):
        binding = ", ".join(v.get("binding_constraints", [])) or "unspecified"
        return f"{tier_note} (capped by capacity: {binding})"
    return f"{tier_note} (not capped)"


def _risk_profile_reasoning(v: dict, m: dict) -> dict:
    return {
        "questionnaire": {
            "version": v.get("questionnaire_version"),
            "answers": v.get("answers"),
            "weighted_score": v.get("stated_score"),
            "stated_tier": v.get("stated_tier"),
        },
        "capacity_layer": {
            "rule_table_version": v.get("rule_table_version"),
            "objective_inputs": {
                "buffer_coverage_months": m.get("buffer_coverage_months"),
                "emi_to_income_ratio": m.get("emi_to_income_ratio"),
                "income_stability": m.get("income_stability"),
                "dependents_count": m.get("dependents_count"),
                "total_life_cover_paise": m.get("total_life_cover_paise"),
                "monthly_income_paise": m.get("monthly_income_paise"),
            },
            "component_ceilings": v.get("capacity_components"),
            "capacity_ceiling": v.get("capacity_ceiling"),
        },
        "final_tier": v.get("final_tier"),
        "capped": v.get("capped"),
        "binding_constraints": v.get("binding_constraints"),
        "unlock_conditions": v.get("unlock_conditions"),
    }


def _allocation_headline(v: dict, m: dict) -> str:
    return f"Target allocation for tier {v.get('final_tier', '?')} (rule table {v.get('rule_table_version', '?')})"


def _allocation_reasoning(v: dict, m: dict) -> dict:
    return {
        "which_tier": v.get("final_tier"),
        "which_rule": v.get("rule_table_version"),
        "rule_lookup_explanation": v.get("reasoning"),
        "target_pct": v.get("target_pct"),
        "current_exposure_pct": v.get("current_exposure_pct"),
        "concentration": v.get("concentration"),
        "config_versions": {
            "asset_classification_config_version": m.get("asset_classification_config_version"),
            "allocation_config_version": m.get("allocation_config_version"),
        },
        "per_holding_classification": v.get("holdings"),
    }


def _debt_leak_headline(v: dict, m: dict) -> str:
    total = v.get("total_recoverable_annual_paise")
    n = len(v.get("leak_components", []) or [])
    return f"{_rupees(total)}/year recoverable across {n} itemized component(s)"


def _debt_leak_reasoning(v: dict, m: dict) -> dict:
    return {
        "total_recoverable_annual_paise": v.get("total_recoverable_annual_paise"),
        "itemized_components": v.get("leak_components"),
        "idle_cash_calculation": v.get("idle_cash"),
        "fee_drag_total_annual_paise": v.get("fee_drag_total_annual_paise"),
        "recurring_candidate_count": v.get("recurring_candidate_count"),
        "data_source_note": v.get("data_source_note"),
        "expense_source_mode": m.get("expense_source_mode"),
        "expense_source_mode_is_explicit": m.get("expense_source_mode_is_explicit"),
    }


def _personalization_headline(v: dict, m: dict) -> str:
    return f"Offset {v.get('offset_pct_points', '?')} pct points from {v.get('edits_considered', '?')} edit(s) (alpha={v.get('alpha', '?')})"


def _personalization_reasoning(v: dict, m: dict) -> dict:
    return {
        "alpha": v.get("alpha"),
        "edits_considered": v.get("edits_considered"),
        "step_by_step_trace": m.get("trace"),
        "base_target_pct": v.get("base_target_pct"),
        "displayed_target_pct": v.get("displayed_target_pct"),
        "capacity_ceiling": v.get("capacity_ceiling"),
        "final_tier": v.get("final_tier"),
    }


DECISION_TYPES: dict[str, DecisionTypeSpec] = {
    "risk_profile": DecisionTypeSpec(
        module_source="risk_profile",
        display_name="Risk tier",
        required_suggested_value_keys=(
            "answers", "questionnaire_version", "stated_score", "stated_tier", "rule_table_version",
            "capacity_ceiling", "capacity_components", "final_tier", "capped", "binding_constraints",
            "unlock_conditions",
        ),
        required_market_context_keys=(
            "buffer_coverage_months", "emi_to_income_ratio", "income_stability", "dependents_count",
            "total_life_cover_paise", "monthly_income_paise",
        ),
        headline=_risk_profile_headline,
        reasoning=_risk_profile_reasoning,
    ),
    "allocation": DecisionTypeSpec(
        module_source="allocation",
        display_name="Target allocation",
        required_suggested_value_keys=("final_tier", "rule_table_version", "reasoning", "target_pct"),
        required_market_context_keys=("asset_classification_config_version", "allocation_config_version"),
        headline=_allocation_headline,
        reasoning=_allocation_reasoning,
    ),
    "debt_leak_engine": DecisionTypeSpec(
        module_source="debt_leak_engine",
        display_name="Recoverable Rs/year",
        required_suggested_value_keys=("total_recoverable_annual_paise", "leak_components", "data_source_note"),
        required_market_context_keys=("expense_source_mode",),
        headline=_debt_leak_headline,
        reasoning=_debt_leak_reasoning,
    ),
    "personalization": DecisionTypeSpec(
        module_source="personalization",
        display_name="Personalization offset",
        required_suggested_value_keys=(
            "offset_pct_points", "alpha", "edits_considered", "base_target_pct", "displayed_target_pct",
        ),
        required_market_context_keys=("trace",),
        headline=_personalization_headline,
        reasoning=_personalization_reasoning,
    ),
}


def _missing_fields(event: SuggestionEvent, spec: DecisionTypeSpec) -> tuple[str, ...]:
    suggested = event.suggested_value or {}
    context = event.market_context or {}
    missing = [k for k in spec.required_suggested_value_keys if k not in suggested]
    missing += [k for k in spec.required_market_context_keys if k not in context]
    return tuple(missing)


def build_trace(event: SuggestionEvent, spec: DecisionTypeSpec | None = None) -> TraceResult:
    spec = spec or DECISION_TYPES.get(event.module_source)
    if spec is None:
        raise UnknownDecisionTypeError(
            f"no transparency spec registered for module_source={event.module_source!r} -- "
            "add a DecisionTypeSpec in transparency.py rather than fabricating a trace for it"
        )

    missing = _missing_fields(event, spec)
    v = event.suggested_value or {}
    m = event.market_context or {}

    if missing:
        headline = (
            f"Cannot fully reconstruct this {spec.display_name.lower()} decision: "
            f"stored event is missing {', '.join(missing)}."
        )
        reasoning = {"partial_suggested_value": v, "partial_market_context": m}
    else:
        headline = spec.headline(v, m)
        reasoning = spec.reasoning(v, m)

    return TraceResult(
        module_source=spec.module_source,
        display_name=spec.display_name,
        framing_label=FRAMING_LABEL,
        event_id=event.event_id,
        timestamp=event.timestamp,
        headline=headline,
        reasoning=reasoning,
        gap_detected=bool(missing),
        missing_fields=missing,
    )


def get_trace(session: Session, user_id: str, module_source: str, event_id: str | None = None) -> TraceResult:
    spec = DECISION_TYPES.get(module_source)
    if spec is None:
        raise UnknownDecisionTypeError(f"unknown decision type {module_source!r}; known types: {sorted(DECISION_TYPES)}")

    if event_id is not None:
        event = session.get(SuggestionEvent, event_id)
        if event is None or event.user_id != user_id or event.module_source != module_source:
            raise NoSuchDecisionEventError(f"no {module_source!r} event id={event_id!r} for user_id={user_id!r}")
    else:
        events = get_user_event_history(session, user_id, module_source=module_source, limit=1)
        if not events:
            raise NoSuchDecisionEventError(f"no {module_source!r} decision found for user_id={user_id!r}")
        event = events[0]

    return build_trace(event, spec)


def list_available_decision_types(session: Session, user_id: str) -> dict[str, int]:
    """How many logged decisions of each known type this user has -- lets
    a caller discover what's traceable without guessing module_source
    values."""
    counts: dict[str, int] = {}
    for module_source in DECISION_TYPES:
        events = get_user_event_history(session, user_id, module_source=module_source, limit=1)
        if events:
            all_events = get_user_event_history(session, user_id, module_source=module_source, limit=500)
            counts[module_source] = len(all_events)
    return counts
