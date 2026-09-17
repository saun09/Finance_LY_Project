"""Module 9: transparency/rule-tracing layer. Reads exclusively from
Module 1's stored suggestion_event data (`suggested_value`,
`market_context`) -- never recomputes a decision to explain it. If a
stored event is missing fields a decision type needs to fully reconstruct
its reasoning, that is reported as a gap (`gap_detected=True`,
`missing_fields`) rather than silently omitted or backfilled with a
freshly computed value, which would defeat the point of tracing what
*actually* drove the stored decision.

LABELING (per the module brief -- read before touching any
`framing_label` or user-facing string here). Two different claims are
made through this module, and they are deliberately NOT the same claim:

  "transparent reasoning" -- Modules 3, 4, 6, 7 and 10. Every one of
  these is a weighted sum or a rule-table lookup, nothing more. Printing
  the weights and the table lookup *is* the whole feature. Never
  "explainable AI" or "AI-powered": that would overclaim what a handful
  of `if` statements and a dict lookup actually are.

  "retrieval explanation" -- Module 5's *local constrained-retrieval*
  pipeline only. There, "which constraint eliminated which candidate
  filing, and why did the returned filing rank first" is a genuine,
  non-trivial, multi-step question with a real multi-step answer. That
  answer is built in modules/rumour_verification/src/transparency.py and
  reaches the app via app/services/rumour_local_engine.py.

  "third-party workflow output" -- Module 5's *n8n* path. That workflow
  is an external LLM pipeline whose prose `reasoning` string is its own
  self-report, not a constraint-elimination trace this project can
  verify or evaluate. It is labeled distinctly so the app never passes it
  off as the explainability claim above. This is the whole reason
  `framing_label` lives on the spec rather than being one module-level
  constant.

This module makes no model calls and never will; see Module 1's original
convention that scoring/cap logic stays pure and deterministic, with no
hidden state.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.services.event_log import (
    count_events_by_module_source,
    get_user_event_history,
    record_suggestion_outcome,
)

# Retained as the default for rule-table/weighted-sum decision types, and
# still asserted on by tests. Specs making a different claim override it.
FRAMING_LABEL = "transparent reasoning"
RETRIEVAL_EXPLANATION_LABEL = "retrieval explanation"
THIRD_PARTY_OUTPUT_LABEL = "third-party workflow output"

#: Labels this module is permitted to stamp on a response. Guarded at
#: import time (see the assertion at the bottom of this file) so that
#: "explainable AI" / "AI-powered" can never appear by accident; a new
#: label has to be added here deliberately.
ALLOWED_FRAMING_LABELS = frozenset(
    {FRAMING_LABEL, RETRIEVAL_EXPLANATION_LABEL, THIRD_PARTY_OUTPUT_LABEL}
)

#: Marker written in place of a reasoning section that cannot be honestly
#: rendered. Machine-readable so the UI can style it, rather than a
#: sentinel string a caller might mistake for real recorded content.
UNAVAILABLE_KEY = "__unavailable__"

#: Reason codes a user may attach when contesting a trace. Kept small and
#: closed so Module 7 can aggregate them; `reason_code` is String(64).
CONTEST_REASON_CODES = (
    "input_wrong",
    "rule_wrong",
    "outcome_unfair",
    "dont_understand",
    "other",
)


# --------------------------------------------------------------------------
# Value hints
#
# The frontend must never guess whether a raw number is paise, a percentage
# or a plain count. Rather than letting the UI infer from key names, the
# server declares the unit for every leaf it emits, from this versioned
# table. The raw value is still what travels over the wire -- a hint is an
# *addition*, never a substitution -- so the audit trace stays faithful to
# what was stored while the UI can render Rs 45,600 next to 4560000.
# --------------------------------------------------------------------------

VALUE_HINT_RULES_VERSION = "v1"

#: Longest/most specific suffix first -- "_pct_points" must beat "_pct".
_SUFFIX_HINTS: tuple[tuple[str, str], ...] = (
    ("_annual_pct", "percent"),
    ("_pct_points", "percent_points"),
    ("_paise", "paise"),
    ("_bps", "basis_points"),
    ("_pct", "percent"),
    ("_months", "months"),
    ("_count", "count"),
    ("_ratio", "ratio"),
    ("_version", "version"),
    ("_date", "date"),
)

#: Exact-key overrides for leaves whose name carries no usable suffix.
_EXACT_HINTS: dict[str, str] = {
    "weighted_score": "score",
    "stated_score": "score",
    "score": "score",
    "matched_score": "score",
    "capacity_ceiling": "tier",
    "final_tier": "tier",
    "stated_tier": "tier",
    "which_tier": "tier",
    "ceiling": "tier",
    "alpha": "ratio",
    "weight": "ratio",
    "confidence": "ratio",
    "buffer_coverage_months": "months",
    "emi_to_income_ratio": "ratio",
    "edits_considered": "count",
    "candidates_considered": "count",
    "candidates_passing": "count",
    "recurring_candidate_count": "count",
    "dependents_count": "count",
    "threshold": "count",
}


def hint_for_key(key: str) -> str | None:
    """The declared unit for one leaf key, or None when the value is plain
    text/boolean and needs no unit."""
    if key in _EXACT_HINTS:
        return _EXACT_HINTS[key]
    for suffix, hint in _SUFFIX_HINTS:
        if key.endswith(suffix):
            return hint
    return None


def build_value_hints(node: Any, out: dict[str, str] | None = None) -> dict[str, str]:
    """Walk a produced reasoning payload and collect `{leaf_key: unit}` for
    every key with a declared unit. Keys are collected by name, not by
    path, because a name always means the same unit across this codebase
    (`*_paise` is paise everywhere, by Module 1's money rule)."""
    out = {} if out is None else out
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                build_value_hints(value, out)
            else:
                hint = hint_for_key(key)
                if hint is not None:
                    out[key] = hint
    elif isinstance(node, list):
        for item in node:
            build_value_hints(item, out)
    return out


# --------------------------------------------------------------------------
# Spec types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReasoningSection:
    """One independently-degradable block of a trace.

    Gap handling is per section rather than per trace: an older event
    missing `unlock_conditions` should cost the reader the capacity block,
    not the questionnaire block that was recorded perfectly well. `build`
    is only ever called once this section's own required keys are present
    and non-null, so it can read them directly instead of hiding gaps
    behind defensive `.get()` chains.
    """

    key: str
    title: str
    build: Callable[[dict, dict], Any]
    requires_value: tuple[str, ...] = ()
    requires_context: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionTypeSpec:
    module_source: str
    display_name: str
    headline: Callable[[dict, dict], str]
    sections: tuple[ReasoningSection, ...]
    framing_label: str = FRAMING_LABEL
    headline_requires_value: tuple[str, ...] = ()
    headline_requires_context: tuple[str, ...] = ()
    #: Surfaced with the trace when this decision type's claim needs
    #: qualifying (e.g. the n8n path's self-reported prose).
    claim_note: str | None = None

    @property
    def required_suggested_value_keys(self) -> tuple[str, ...]:
        keys: list[str] = list(self.headline_requires_value)
        for section in self.sections:
            keys += section.requires_value
        return tuple(dict.fromkeys(keys))

    @property
    def required_market_context_keys(self) -> tuple[str, ...]:
        keys: list[str] = list(self.headline_requires_context)
        for section in self.sections:
            keys += section.requires_context
        return tuple(dict.fromkeys(keys))


@dataclass(frozen=True)
class SectionResult:
    key: str
    title: str
    available: bool
    missing_fields: tuple[str, ...]


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
    sections: tuple[SectionResult, ...] = ()
    value_hints: dict[str, str] = field(default_factory=dict)
    value_hint_rules_version: str = VALUE_HINT_RULES_VERSION
    claim_note: str | None = None
    contested: bool = False
    contest_reason_code: str | None = None


@dataclass(frozen=True)
class DecisionEventSummary:
    """One row in a decision's history list -- enough to choose which event
    to trace without fetching every full trace."""

    event_id: str
    timestamp: datetime
    module_source: str
    display_name: str
    headline: str
    gap_detected: bool
    contested: bool


@dataclass(frozen=True)
class FieldChange:
    path: str
    before: Any
    after: Any
    hint: str | None


@dataclass(frozen=True)
class TraceComparison:
    module_source: str
    display_name: str
    framing_label: str
    before_event_id: str
    after_event_id: str
    before_timestamp: datetime
    after_timestamp: datetime
    before_headline: str
    after_headline: str
    changes: tuple[FieldChange, ...]
    unchanged_field_count: int
    value_hints: dict[str, str]


class NoSuchDecisionEventError(ValueError):
    pass


class UnknownDecisionTypeError(ValueError):
    pass


class InvalidContestReasonError(ValueError):
    pass


def _rupees(paise) -> str:
    try:
        return f"Rs {int(paise) / 100:,.0f}"
    except (TypeError, ValueError):
        return "Rs ?"


# --------------------------------------------------------------------------
# Module 3 -- risk tier
# --------------------------------------------------------------------------


def _risk_profile_headline(v: dict, m: dict) -> str:
    tier_note = f"stated tier {v['stated_tier']} -> final tier {v['final_tier']}"
    if v["capped"]:
        binding = ", ".join(v.get("binding_constraints") or []) or "unspecified"
        return f"{tier_note} (capped by capacity: {binding})"
    return f"{tier_note} (not capped)"


def _risk_questionnaire_section(v: dict, m: dict) -> dict:
    return {
        "version": v["questionnaire_version"],
        "answers": v["answers"],
        "weighted_score": v["stated_score"],
        "stated_tier": v["stated_tier"],
    }


def _risk_capacity_section(v: dict, m: dict) -> dict:
    return {
        "rule_table_version": v["rule_table_version"],
        "objective_inputs": {
            "buffer_coverage_months": m["buffer_coverage_months"],
            "emi_to_income_ratio": m["emi_to_income_ratio"],
            "income_stability": m["income_stability"],
            "dependents_count": m["dependents_count"],
            "total_life_cover_paise": m["total_life_cover_paise"],
            "monthly_income_paise": m["monthly_income_paise"],
        },
        "component_ceilings": v["capacity_components"],
        "capacity_ceiling": v["capacity_ceiling"],
    }


def _risk_outcome_section(v: dict, m: dict) -> dict:
    return {
        "final_tier": v["final_tier"],
        "capped": v["capped"],
        "binding_constraints": v["binding_constraints"],
        "unlock_conditions": v["unlock_conditions"],
    }


# --------------------------------------------------------------------------
# Module 4 -- target allocation
# --------------------------------------------------------------------------


def _allocation_headline(v: dict, m: dict) -> str:
    return f"Target allocation for tier {v['final_tier']} (rule table {v['rule_table_version']})"


def _allocation_rule_section(v: dict, m: dict) -> dict:
    return {
        "which_tier": v["final_tier"],
        "which_rule": v["rule_table_version"],
        "rule_lookup_explanation": v["reasoning"],
        "target_pct": v["target_pct"],
    }


def _allocation_position_section(v: dict, m: dict) -> dict:
    return {
        "current_exposure_pct": v.get("current_exposure_pct"),
        "concentration": v.get("concentration"),
        "per_holding_classification": v.get("holdings"),
    }


def _allocation_config_section(v: dict, m: dict) -> dict:
    return {
        "asset_classification_config_version": m["asset_classification_config_version"],
        "allocation_config_version": m["allocation_config_version"],
    }


# --------------------------------------------------------------------------
# Module 6 -- recoverable Rs/year
# --------------------------------------------------------------------------


def _debt_leak_headline(v: dict, m: dict) -> str:
    total = v["total_recoverable_annual_paise"]
    n = len(v["leak_components"] or [])
    return f"{_rupees(total)}/year recoverable across {n} itemized component(s)"


def _debt_leak_total_section(v: dict, m: dict) -> dict:
    return {
        "total_recoverable_annual_paise": v["total_recoverable_annual_paise"],
        "itemized_components": v["leak_components"],
    }


def _debt_leak_detail_section(v: dict, m: dict) -> dict:
    return {
        "idle_cash_calculation": v.get("idle_cash"),
        "fee_drag_total_annual_paise": v.get("fee_drag_total_annual_paise"),
        "recurring_candidate_count": v.get("recurring_candidate_count"),
    }


def _debt_leak_provenance_section(v: dict, m: dict) -> dict:
    return {
        "data_source_note": v["data_source_note"],
        "expense_source_mode": m["expense_source_mode"],
        "expense_source_mode_is_explicit": m.get("expense_source_mode_is_explicit"),
    }


# --------------------------------------------------------------------------
# Module 7 -- personalization offset
# --------------------------------------------------------------------------


def _personalization_headline(v: dict, m: dict) -> str:
    return (
        f"Offset {v['offset_pct_points']} pct points from "
        f"{v['edits_considered']} edit(s) (alpha={v['alpha']})"
    )


def _personalization_inputs_section(v: dict, m: dict) -> dict:
    return {"alpha": v["alpha"], "edits_considered": v["edits_considered"]}


def _personalization_trace_section(v: dict, m: dict) -> list:
    return m["trace"]


def _personalization_effect_section(v: dict, m: dict) -> dict:
    return {
        "base_target_pct": v["base_target_pct"],
        "displayed_target_pct": v["displayed_target_pct"],
        "capacity_ceiling": v.get("capacity_ceiling"),
        "final_tier": v.get("final_tier"),
    }


# --------------------------------------------------------------------------
# Module 10 -- gamification milestone
#
# Milestones are awarded by a threshold table (see gamification_config.py),
# which makes "why didn't I get this one?" exactly the kind of dispute a
# rule trace settles. Effort-only categories are enforced at import time in
# that module, not here -- this view just prints which threshold was crossed.
# --------------------------------------------------------------------------


def _gamification_headline(v: dict, m: dict) -> str:
    return f"{v['headline']} (milestone {v['milestone_id']}, category {v['category']})"


def _gamification_rule_section(v: dict, m: dict) -> dict:
    return {
        "milestone_id": v["milestone_id"],
        "category": v["category"],
        "headline": v["headline"],
        "threshold_inputs": v["details"],
        "config_version": m["config_version"],
    }


# --------------------------------------------------------------------------
# Module 5 -- rumour verification (n8n workflow path)
#
# Deliberately NOT labeled as an explanation. The trace below reports what
# the external workflow returned and how much of it was usable; the prose
# `reasoning` string is the workflow's own self-report. The genuine
# constraint-elimination explanation is the local engine's, surfaced
# through rumour_local_engine.py with RETRIEVAL_EXPLANATION_LABEL.
# --------------------------------------------------------------------------


N8N_CLAIM_NOTE = (
    "Produced by an external n8n LLM workflow. The reasoning text below is "
    "that workflow's own self-report, not a constraint-elimination trace "
    "this project computed or evaluated. For the explainable retrieval "
    "path -- which constraint eliminated which candidate filing, and why "
    "the returned filing ranked first -- use the local engine."
)


def _rumour_headline(v: dict, m: dict) -> str:
    status = v["status"] or "no verdict"
    matched = v.get("matched_filing")
    where = f"matched {matched['filing_id']}" if matched else "no filing matched"
    return f"Verdict: {status} ({where}, {v['candidates_considered']} evidence item(s) considered)"


def _rumour_claim_section(v: dict, m: dict) -> dict:
    return {
        "query_text": v["query_text"],
        "rumour_date": v.get("rumour_date"),
        "status": v["status"],
        "matched_score": v.get("matched_score"),
        "matched_filing": v.get("matched_filing"),
    }


def _rumour_evidence_section(v: dict, m: dict) -> dict:
    return {
        "candidates_considered": v["candidates_considered"],
        "candidates_passing": v["candidates_passing"],
        "official_evidence_count": m["official_evidence_count"],
        "news_evidence_count": m["news_evidence_count"],
    }


def _rumour_workflow_section(v: dict, m: dict) -> dict:
    return {
        "engine": m["engine"],
        "workflow_self_reported_reasons": v["top_candidate_reasons"],
        "eliminated_candidates_available": False,
        "why_not": (
            "This engine returns a verdict and prose, not a per-candidate "
            "constraint trace, so eliminated candidates cannot be listed."
        ),
    }


# --------------------------------------------------------------------------
# Module 5 -- rumour verification (local constrained-retrieval path)
#
# The one decision type in this registry that earns "explanation" language.
# Everything else here is a weighted sum or a table lookup; this is a
# two-stage retrieval pipeline where a candidate can be eliminated by any
# one of three independent constraints, so "why this filing and not that
# one" is a real question with a real answer. See
# app/services/rumour_local_engine.py and
# modules/rumour_verification/src/transparency.py.
# --------------------------------------------------------------------------


LOCAL_ENGINE_CLAIM_NOTE = (
    "Produced by this project's own constrained-retrieval pipeline: TF-IDF "
    "ranking, then three independent constraint checks (entity, temporal, "
    "source-authority). Every candidate considered is listed below with the "
    "constraint that eliminated it. Still not a model -- cosine similarity "
    "and three rule-based filters -- but the elimination trace is computed "
    "and checkable, not self-reported."
)


def _rumour_local_headline(v: dict, m: dict) -> str:
    matched = v.get("matched_filing")
    where = f"matched {matched['filing_id']}" if matched else "no filing matched"
    return (
        f"Verdict: {v['status'] or 'no match'} ({where}); "
        f"{v['candidates_eliminated']} of {v['candidates_considered']} candidates eliminated by constraint"
    )


def _rumour_local_claim_section(v: dict, m: dict) -> dict:
    return {
        "query_text": v["query_text"],
        "rumour_date": v.get("rumour_date"),
        "status": v["status"],
        "matched_score": v.get("matched_score"),
        "matched_filing": v.get("matched_filing"),
    }


def _rumour_local_winner_section(v: dict, m: dict) -> dict:
    return {
        "why_ranked_first": v["why_ranked_first"],
        "candidates_considered": v["candidates_considered"],
        "candidates_passing": v["candidates_passing"],
        "candidates_eliminated": v["candidates_eliminated"],
    }


def _rumour_local_elimination_section(v: dict, m: dict) -> dict:
    return {
        "constraints_applied": m["constraints_applied"],
        "eliminated_by_constraint": v["eliminated_by_constraint"],
        "per_candidate": v["candidate_explanations"],
    }


def _rumour_local_engine_section(v: dict, m: dict) -> dict:
    return {
        "engine": m["engine"],
        "corpus_size": m["corpus_size"],
        "full_trace_text": v["full_trace_text"],
    }


DECISION_TYPES: dict[str, DecisionTypeSpec] = {
    "risk_profile": DecisionTypeSpec(
        module_source="risk_profile",
        display_name="Risk tier",
        headline=_risk_profile_headline,
        headline_requires_value=("stated_tier", "final_tier", "capped"),
        sections=(
            ReasoningSection(
                key="questionnaire",
                title="What you told us (willingness)",
                build=_risk_questionnaire_section,
                requires_value=("questionnaire_version", "answers", "stated_score", "stated_tier"),
            ),
            ReasoningSection(
                key="capacity_layer",
                title="What your finances allow (ability)",
                build=_risk_capacity_section,
                requires_value=("rule_table_version", "capacity_components", "capacity_ceiling"),
                requires_context=(
                    "buffer_coverage_months", "emi_to_income_ratio", "income_stability",
                    "dependents_count", "total_life_cover_paise", "monthly_income_paise",
                ),
            ),
            ReasoningSection(
                key="outcome",
                title="The tier you got, and how to lift it",
                build=_risk_outcome_section,
                requires_value=("final_tier", "capped", "binding_constraints", "unlock_conditions"),
            ),
        ),
    ),
    "allocation": DecisionTypeSpec(
        module_source="allocation",
        display_name="Target allocation",
        headline=_allocation_headline,
        headline_requires_value=("final_tier", "rule_table_version"),
        sections=(
            ReasoningSection(
                key="rule_lookup",
                title="Which tier, which rule table",
                build=_allocation_rule_section,
                requires_value=("final_tier", "rule_table_version", "reasoning", "target_pct"),
            ),
            ReasoningSection(
                key="current_position",
                title="Where your portfolio stands today",
                build=_allocation_position_section,
                requires_value=("current_exposure_pct", "concentration", "holdings"),
            ),
            ReasoningSection(
                key="config_versions",
                title="Which config versions applied",
                build=_allocation_config_section,
                requires_context=("asset_classification_config_version", "allocation_config_version"),
            ),
        ),
    ),
    "debt_leak_engine": DecisionTypeSpec(
        module_source="debt_leak_engine",
        display_name="Recoverable Rs/year",
        headline=_debt_leak_headline,
        headline_requires_value=("total_recoverable_annual_paise", "leak_components"),
        sections=(
            ReasoningSection(
                key="recoverable_total",
                title="The headline figure, itemized",
                build=_debt_leak_total_section,
                requires_value=("total_recoverable_annual_paise", "leak_components"),
            ),
            ReasoningSection(
                key="component_detail",
                title="How each component was computed",
                build=_debt_leak_detail_section,
                requires_value=("idle_cash", "fee_drag_total_annual_paise", "recurring_candidate_count"),
            ),
            ReasoningSection(
                key="data_provenance",
                title="Where the expense data came from",
                build=_debt_leak_provenance_section,
                requires_value=("data_source_note",),
                requires_context=("expense_source_mode",),
            ),
        ),
    ),
    "personalization": DecisionTypeSpec(
        module_source="personalization",
        display_name="Personalization offset",
        headline=_personalization_headline,
        headline_requires_value=("offset_pct_points", "edits_considered", "alpha"),
        sections=(
            ReasoningSection(
                key="inputs",
                title="Learning rate and edits considered",
                build=_personalization_inputs_section,
                requires_value=("alpha", "edits_considered"),
            ),
            ReasoningSection(
                key="step_by_step_trace",
                title="Each edit's contribution, in order",
                build=_personalization_trace_section,
                requires_context=("trace",),
            ),
            ReasoningSection(
                key="effect",
                title="What the offset changed",
                build=_personalization_effect_section,
                requires_value=("base_target_pct", "displayed_target_pct"),
            ),
        ),
    ),
    "gamification": DecisionTypeSpec(
        module_source="gamification",
        display_name="Milestone awarded",
        headline=_gamification_headline,
        headline_requires_value=("headline", "milestone_id", "category"),
        sections=(
            ReasoningSection(
                key="threshold_rule",
                title="Which threshold was crossed",
                build=_gamification_rule_section,
                requires_value=("milestone_id", "category", "headline", "details"),
                requires_context=("config_version",),
            ),
        ),
    ),
    "rumour_verification": DecisionTypeSpec(
        module_source="rumour_verification",
        display_name="Rumour verification",
        framing_label=THIRD_PARTY_OUTPUT_LABEL,
        claim_note=N8N_CLAIM_NOTE,
        headline=_rumour_headline,
        headline_requires_value=("status", "candidates_considered"),
        sections=(
            ReasoningSection(
                key="claim",
                title="The claim and what it matched",
                build=_rumour_claim_section,
                requires_value=("query_text", "status"),
            ),
            ReasoningSection(
                key="evidence_counts",
                title="How much evidence was returned",
                build=_rumour_evidence_section,
                requires_value=("candidates_considered", "candidates_passing"),
                requires_context=("official_evidence_count", "news_evidence_count"),
            ),
            ReasoningSection(
                key="workflow_output",
                title="What the external workflow reported",
                build=_rumour_workflow_section,
                requires_value=("top_candidate_reasons",),
                requires_context=("engine",),
            ),
        ),
    ),
    "rumour_verification_local": DecisionTypeSpec(
        module_source="rumour_verification_local",
        display_name="Rumour verification (explainable retrieval)",
        framing_label=RETRIEVAL_EXPLANATION_LABEL,
        claim_note=LOCAL_ENGINE_CLAIM_NOTE,
        headline=_rumour_local_headline,
        headline_requires_value=("status", "candidates_considered", "candidates_eliminated"),
        sections=(
            ReasoningSection(
                key="claim",
                title="The claim and what it matched",
                build=_rumour_local_claim_section,
                requires_value=("query_text", "status"),
            ),
            ReasoningSection(
                key="why_this_filing_won",
                title="Why the returned filing ranked first",
                build=_rumour_local_winner_section,
                requires_value=(
                    "why_ranked_first", "candidates_considered",
                    "candidates_passing", "candidates_eliminated",
                ),
            ),
            ReasoningSection(
                key="eliminations",
                title="Which constraint eliminated which candidate",
                build=_rumour_local_elimination_section,
                requires_value=("eliminated_by_constraint", "candidate_explanations"),
                requires_context=("constraints_applied",),
            ),
            ReasoningSection(
                key="engine",
                title="Engine and corpus",
                build=_rumour_local_engine_section,
                requires_value=("full_trace_text",),
                requires_context=("engine", "corpus_size"),
            ),
        ),
    ),
}


# --------------------------------------------------------------------------
# Gap detection
# --------------------------------------------------------------------------


def _absent(store: dict, key: str) -> bool:
    """A key is missing if it is absent OR stored as null.

    Presence-only checking would let `{"final_tier": null}` render as
    "stated tier None -> final tier None", which reads like a real trace
    but explains nothing. An empty list or 0 is a real recorded value
    (`binding_constraints: []` legitimately means "nothing was binding")
    and is NOT treated as missing.
    """
    return key not in store or store[key] is None


def _section_missing(section: ReasoningSection, v: dict, m: dict) -> tuple[str, ...]:
    missing = [k for k in section.requires_value if _absent(v, k)]
    missing += [k for k in section.requires_context if _absent(m, k)]
    return tuple(missing)


def _headline_missing(spec: DecisionTypeSpec, v: dict, m: dict) -> tuple[str, ...]:
    missing = [k for k in spec.headline_requires_value if _absent(v, k)]
    missing += [k for k in spec.headline_requires_context if _absent(m, k)]
    return tuple(missing)


def _missing_fields(event: SuggestionEvent, spec: DecisionTypeSpec) -> tuple[str, ...]:
    """Every required field this stored event lacks, across all sections."""
    v = event.suggested_value or {}
    m = event.market_context or {}
    missing: list[str] = list(_headline_missing(spec, v, m))
    for section in spec.sections:
        missing += _section_missing(section, v, m)
    return tuple(dict.fromkeys(missing))


def _unavailable_section(section: ReasoningSection, missing: tuple[str, ...], v: dict, m: dict) -> dict:
    """Stand-in for a section that cannot be honestly rendered. Still
    surfaces whichever of that section's own fields WERE recorded, so a
    partial event degrades to partial information rather than to nothing."""
    recorded = {k: v[k] for k in section.requires_value if not _absent(v, k)}
    recorded.update({k: m[k] for k in section.requires_context if not _absent(m, k)})
    return {
        UNAVAILABLE_KEY: True,
        "missing_fields": list(missing),
        "recorded_values": recorded,
    }


def build_trace(event: SuggestionEvent, spec: DecisionTypeSpec | None = None) -> TraceResult:
    spec = spec or DECISION_TYPES.get(event.module_source)
    if spec is None:
        raise UnknownDecisionTypeError(
            f"no transparency spec registered for module_source={event.module_source!r} -- "
            "add a DecisionTypeSpec in transparency.py rather than fabricating a trace for it"
        )

    v = event.suggested_value or {}
    m = event.market_context or {}

    headline_missing = _headline_missing(spec, v, m)
    if headline_missing:
        headline = (
            f"Cannot fully reconstruct this {spec.display_name.lower()} decision: "
            f"stored event is missing {', '.join(headline_missing)}."
        )
    else:
        headline = spec.headline(v, m)

    reasoning: dict = {}
    section_results: list[SectionResult] = []
    all_missing: list[str] = list(headline_missing)

    for section in spec.sections:
        missing = _section_missing(section, v, m)
        all_missing += missing
        if missing:
            reasoning[section.key] = _unavailable_section(section, missing, v, m)
        else:
            reasoning[section.key] = section.build(v, m)
        section_results.append(
            SectionResult(
                key=section.key,
                title=section.title,
                available=not missing,
                missing_fields=missing,
            )
        )

    missing_fields = tuple(dict.fromkeys(all_missing))

    return TraceResult(
        module_source=spec.module_source,
        display_name=spec.display_name,
        framing_label=spec.framing_label,
        event_id=event.event_id,
        timestamp=event.timestamp,
        headline=headline,
        reasoning=reasoning,
        gap_detected=bool(missing_fields),
        missing_fields=missing_fields,
        sections=tuple(section_results),
        value_hints=build_value_hints(reasoning),
        value_hint_rules_version=VALUE_HINT_RULES_VERSION,
        claim_note=spec.claim_note,
        contested=event.action_taken == ActionTaken.REJECTED,
        contest_reason_code=event.reason_code,
    )


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def _require_spec(module_source: str) -> DecisionTypeSpec:
    spec = DECISION_TYPES.get(module_source)
    if spec is None:
        raise UnknownDecisionTypeError(
            f"unknown decision type {module_source!r}; known types: {sorted(DECISION_TYPES)}"
        )
    return spec


def _load_event(session: Session, user_id: str, module_source: str, event_id: str) -> SuggestionEvent:
    event = session.get(SuggestionEvent, event_id)
    if event is None or event.user_id != user_id or event.module_source != module_source:
        raise NoSuchDecisionEventError(
            f"no {module_source!r} event id={event_id!r} for user_id={user_id!r}"
        )
    return event


def get_trace(session: Session, user_id: str, module_source: str, event_id: str | None = None) -> TraceResult:
    spec = _require_spec(module_source)

    if event_id is not None:
        event = _load_event(session, user_id, module_source, event_id)
    else:
        events = get_user_event_history(session, user_id, module_source=module_source, limit=1)
        if not events:
            raise NoSuchDecisionEventError(f"no {module_source!r} decision found for user_id={user_id!r}")
        event = events[0]

    return build_trace(event, spec)


def list_available_decision_types(session: Session, user_id: str) -> dict[str, int]:
    """How many logged decisions of each known type this user has -- lets a
    caller discover what's traceable without guessing module_source values.

    One grouped COUNT query for every type at once, so the number is exact
    at any history length rather than capped by a fetch limit.
    """
    counts = count_events_by_module_source(session, user_id, module_sources=tuple(DECISION_TYPES))
    return {source: n for source, n in counts.items() if n > 0}


def list_decision_events(
    session: Session, user_id: str, module_source: str, limit: int = 50, offset: int = 0
) -> list[DecisionEventSummary]:
    """This user's decision history for one type, newest first.

    Every decision was already stored by Module 1; without this the app can
    only ever show the latest one, and "my tier changed last month -- what
    moved?" is unanswerable despite the data being right there.
    """
    spec = _require_spec(module_source)
    events = get_user_event_history(
        session, user_id, module_source=module_source, limit=limit, offset=offset
    )
    summaries = []
    for event in events:
        trace = build_trace(event, spec)
        summaries.append(
            DecisionEventSummary(
                event_id=trace.event_id,
                timestamp=trace.timestamp,
                module_source=trace.module_source,
                display_name=trace.display_name,
                headline=trace.headline,
                gap_detected=trace.gap_detected,
                contested=trace.contested,
            )
        )
    return summaries


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------


def _walk_leaves(node: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _walk_leaves(value, f"{prefix}.{key}" if prefix else key, out)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk_leaves(item, f"{prefix}[{i}]", out)
    else:
        out[prefix] = node


def _leaf_key(path: str) -> str:
    tail = path.split(".")[-1]
    return tail.split("[")[0]


def diff_traces(before: TraceResult, after: TraceResult) -> tuple[tuple[FieldChange, ...], int]:
    """Every leaf field that differs between two traces of the same type.

    Pure comparison of two already-built traces -- like everything else
    here it reads stored data and never recomputes either decision.
    """
    before_leaves: dict[str, Any] = {}
    after_leaves: dict[str, Any] = {}
    _walk_leaves(before.reasoning, "", before_leaves)
    _walk_leaves(after.reasoning, "", after_leaves)

    changes: list[FieldChange] = []
    unchanged = 0
    for path in sorted(set(before_leaves) | set(after_leaves)):
        b = before_leaves.get(path)
        a = after_leaves.get(path)
        if b == a:
            unchanged += 1
            continue
        changes.append(FieldChange(path=path, before=b, after=a, hint=hint_for_key(_leaf_key(path))))
    return tuple(changes), unchanged


def compare_traces(
    session: Session, user_id: str, module_source: str, before_event_id: str, after_event_id: str
) -> TraceComparison:
    spec = _require_spec(module_source)
    before = build_trace(_load_event(session, user_id, module_source, before_event_id), spec)
    after = build_trace(_load_event(session, user_id, module_source, after_event_id), spec)

    changes, unchanged = diff_traces(before, after)
    hints = dict(before.value_hints)
    hints.update(after.value_hints)

    return TraceComparison(
        module_source=spec.module_source,
        display_name=spec.display_name,
        framing_label=spec.framing_label,
        before_event_id=before.event_id,
        after_event_id=after.event_id,
        before_timestamp=before.timestamp,
        after_timestamp=after.timestamp,
        before_headline=before.headline,
        after_headline=after.headline,
        changes=changes,
        unchanged_field_count=unchanged,
        value_hints=hints,
    )


# --------------------------------------------------------------------------
# Contest
# --------------------------------------------------------------------------


def contest_decision(
    session: Session,
    user_id: str,
    module_source: str,
    event_id: str,
    reason_code: str,
    note: str | None = None,
    commit: bool = True,
) -> TraceResult:
    """Record that the user disputes this decision's reasoning.

    A trace the user can read but not answer back to is a one-way mirror.
    This writes through Module 1's existing outcome fields rather than
    inventing a parallel store, so a contest is one more
    `action_taken=REJECTED` row in the same event log Module 7 already
    learns from -- the objection feeds the feedback loop instead of dying
    in a support inbox.
    """
    spec = _require_spec(module_source)
    if reason_code not in CONTEST_REASON_CODES:
        raise InvalidContestReasonError(
            f"unknown contest reason_code {reason_code!r}; allowed: {list(CONTEST_REASON_CODES)}"
        )

    event = _load_event(session, user_id, module_source, event_id)
    record_suggestion_outcome(
        session,
        event_id=event.event_id,
        action_taken=ActionTaken.REJECTED,
        reason_code=reason_code,
        delta={"contested_via": "transparency_trace", "contest_note": note} if note else {"contested_via": "transparency_trace"},
        commit=commit,
    )
    session.refresh(event)
    return build_trace(event, spec)


# --------------------------------------------------------------------------
# Import-time guards
# --------------------------------------------------------------------------

for _source, _spec in DECISION_TYPES.items():
    assert _spec.module_source == _source, f"DECISION_TYPES key {_source!r} != spec.module_source"
    assert _spec.framing_label in ALLOWED_FRAMING_LABELS, (
        f"{_source!r} declares framing_label {_spec.framing_label!r}, which is not in "
        "ALLOWED_FRAMING_LABELS. Adding a label is a deliberate act -- see this module's docstring."
    )
    _lowered = _spec.framing_label.lower()
    assert "ai" not in _lowered.split() and "explainable" not in _lowered, (
        f"{_source!r} framing_label {_spec.framing_label!r} claims AI/explainability. "
        "Module 9 prints weights and rule tables; it does not run models."
    )
del _source, _spec, _lowered
