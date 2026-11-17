"""Reproducible faithfulness checks for risk explanations and production RFs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import re
import sqlite3
import sys
import warnings
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
import shap
import sklearn
from scipy import stats
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
for import_path in (ROOT, BACKEND_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.services.risk_profile import (  # noqa: E402
    CapacityInputs,
    IncomeStabilityValue,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import (  # noqa: E402
    CAPACITY_RULE_TABLE_V1,
    QUESTIONNAIRE_V1,
    QUESTIONNAIRE_V2,
)
from app.services.transparency import build_trace  # noqa: E402
from app.services.model_artifacts import load_versioned_model  # noqa: E402
from research_artifacts.experiments.common import capacity_inputs_from_profile  # noqa: E402
from scripts.train_risk_tier_reduced_model import load_training_rows  # noqa: E402


# All analysis and reproducibility parameters are kept in this block.
CONFIG: dict[str, Any] = {
    "seed": 42,
    "cohort_path": ROOT / "research_artifacts" / "experiments" / "results" / "cohort.csv",
    "database_path": ROOT / "backend" / "dev.db",
    "results_dir": ROOT / "research_artifacts" / "experiments" / "results",
    "user_study_dir": ROOT / "research_artifacts" / "experiments" / "user_study",
    "full_model_path": ROOT / "backend" / "app" / "ml_models" / "risk_tier_rf.pkl",
    "reduced_model_path": ROOT / "backend" / "app" / "ml_models" / "risk_tier_rf_reduced_4items.pkl",
    "bootstrap_replicates": 2000,
    "bootstrap_seed": 20261108,
    "test_split_fraction": 0.20,
    "test_split_seed": 42,
    "shap_background_size": 40,
    "shap_background_seed": 42,
    "shap_additivity_tolerance": 1e-5,
    "deletion_top_k": 2,
    "random_feature_draws": 20,
    "stability_replicates": 1000,
    "stability_seed": 20261109,
    "ci_level": 0.95,
    "plot_dpi": 160,
    "scenario_categories": (
        "capped_emi_only",
        "uncapped_able_but_unwilling",
        "tied_constraints",
        "capped_buffer_only",
        "capped_insurance_only",
        "uncapped_aligned",
    ),
    "suspect_emi_boundary_case": {
        "monthly_income_rupees": 100000,
        "monthly_emi_rupees": 45000,
        "essential_expense_rupees": 20000,
        "cash_buffer_months": 6,
        "requested_reduction_rupees": 25001,
    },
}

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "full_7items": (
        "horizon",
        "drawdown_reaction",
        "experience",
        "goal",
        "windfall_allocation",
        "sure_gain_tradeoff",
        "friend_description",
    ),
    "reduced_4items": (
        "windfall_allocation",
        "friend_description",
        "drawdown_reaction",
        "sure_gain_tradeoff",
    ),
}
FEATURE_LABELS = {
    "horizon": "Investment horizon",
    "drawdown_reaction": "Drawdown reaction",
    "experience": "Investment experience",
    "goal": "Primary goal",
    "windfall_allocation": "Windfall allocation",
    "sure_gain_tradeoff": "Sure-gain trade-off",
    "friend_description": "Friend description",
}
CONTEXT_FIELDS = (
    "buffer_coverage_months",
    "emi_to_income_ratio",
    "income_stability",
    "dependents_count",
    "total_life_cover_paise",
    "monthly_income_paise",
    "cash_balance_paise",
    "essential_monthly_expense_paise",
    "total_monthly_emi_paise",
)


def bootstrap_mean_ci(
    values: list[float] | np.ndarray,
    seed: int,
    replicates: int | None = None,
) -> tuple[float, float, float]:
    """Return a mean and percentile bootstrap confidence interval."""
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        return math.nan, math.nan, math.nan
    data = data[np.isfinite(data)]
    if data.size == 0:
        return math.nan, math.nan, math.nan
    n_replicates = int(replicates or CONFIG["bootstrap_replicates"])
    rng = np.random.default_rng(seed)
    boot_means = np.empty(n_replicates, dtype=float)
    chunk_size = max(1, min(100, n_replicates))
    for start in range(0, n_replicates, chunk_size):
        end = min(start + chunk_size, n_replicates)
        indices = rng.integers(0, data.size, size=(end - start, data.size))
        boot_means[start:end] = data[indices].mean(axis=1)
    tail = (1.0 - float(CONFIG["ci_level"])) / 2.0
    low, high = np.quantile(boot_means, [tail, 1.0 - tail])
    return float(data.mean()), float(low), float(high)


def _read_cohort(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    numeric_fields = {
        "monthly_income",
        "essential_monthly_expense",
        "other_monthly_expense",
        "liquid_cash",
        "total_monthly_emi",
        "dependents_count",
        "total_life_cover",
        "investable_assets",
    }
    for row in rows:
        for field in numeric_fields:
            row[field] = int(float(row[field]))
    return rows


def _capacity_inputs_from_context(context: dict[str, Any]) -> CapacityInputs:
    missing = [field for field in CONTEXT_FIELDS if field not in context or context[field] is None]
    if missing:
        raise ValueError(f"missing capacity inputs: {', '.join(missing)}")
    return CapacityInputs(
        buffer_coverage_months=Decimal(str(context["buffer_coverage_months"])),
        emi_to_income_ratio=Decimal(str(context["emi_to_income_ratio"])),
        income_stability=IncomeStabilityValue(str(context["income_stability"])),
        dependents_count=int(context["dependents_count"]),
        total_life_cover_paise=int(context["total_life_cover_paise"]),
        monthly_income_paise=int(context["monthly_income_paise"]),
        cash_balance_paise=int(context["cash_balance_paise"]),
        essential_monthly_expense_paise=int(context["essential_monthly_expense_paise"]),
        total_monthly_emi_paise=int(context["total_monthly_emi_paise"]),
    )


def replay_logged_decision(
    suggested_value: dict[str, Any],
    market_context: dict[str, Any],
) -> dict[str, Any]:
    """Replay the decision using only questionnaire answers and recorded inputs."""
    version = suggested_value.get("questionnaire_version")
    questionnaires = {
        QUESTIONNAIRE_V1.version: QUESTIONNAIRE_V1,
        QUESTIONNAIRE_V2.version: QUESTIONNAIRE_V2,
    }
    if version not in questionnaires:
        raise ValueError(f"unsupported questionnaire version: {version!r}")
    questionnaire = questionnaires[version]
    answers = suggested_value.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("missing questionnaire answers")
    missing_answers = [q.id for q in questionnaire.questions if q.id not in answers]
    if missing_answers:
        raise ValueError(f"missing questionnaire answers: {', '.join(missing_answers)}")
    stated = compute_stated_tier(
        {question_id: str(answer) for question_id, answer in answers.items()},
        questionnaire,
    )
    inputs = _capacity_inputs_from_context(market_context)
    capacity = compute_capacity_ceiling(inputs)
    final = compute_final_tier(stated, capacity, inputs)
    return {
        "stated_tier": stated.tier,
        "capacity_ceiling": capacity.ceiling,
        "final_tier": final.final_tier,
        "binding_constraints": list(final.binding_constraints),
        "capacity_components": [asdict(component) for component in capacity.components],
    }


def compare_logged_decision(
    suggested_value: dict[str, Any],
    market_context: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return the replay and its missing-input/output or value mismatches."""
    mismatches: list[str] = []
    try:
        replay = replay_logged_decision(suggested_value, market_context)
    except (ValueError, KeyError, TypeError) as error:
        return None, [f"replay_not_possible: {error}"]
    for field in ("stated_tier", "capacity_ceiling", "final_tier"):
        if field not in suggested_value:
            mismatches.append(f"{field}: missing logged output")
        elif int(suggested_value[field]) != replay[field]:
            mismatches.append(
                f"{field}: logged={suggested_value[field]!r}, replayed={replay[field]!r}"
            )
    logged_bindings = suggested_value.get("binding_constraints")
    if logged_bindings is None:
        mismatches.append("binding_constraints: missing logged output")
    elif sorted(logged_bindings) != sorted(replay["binding_constraints"]):
        mismatches.append(
            "binding_constraints: "
            f"logged={sorted(logged_bindings)!r}, replayed={sorted(replay['binding_constraints'])!r}"
        )
    return replay, mismatches


def _trace_completeness_gap(trace: Any, replay_mismatches: list[str]) -> tuple[bool, tuple[str, ...]]:
    replay_not_possible = any(
        mismatch.startswith("replay_not_possible:")
        for mismatch in replay_mismatches
    )
    fields = tuple(
        dict.fromkeys(
            (
                *trace.missing_fields,
                *(("replay_not_possible",) if replay_not_possible else ()),
            )
        )
    )
    return bool(trace.gap_detected or replay_not_possible), fields


def make_explanation_event(
    event_id: str,
    suggested_value: dict[str, Any],
    market_context: dict[str, Any],
    timestamp: datetime | str | None = None,
) -> SimpleNamespace:
    """Create an in-memory event for transparency.build_trace; never writes DB."""
    return SimpleNamespace(
        event_id=event_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        module_source="risk_profile",
        suggested_value=suggested_value,
        market_context=market_context,
        delta=None,
        reason_code=None,
    )


def _profile_decision(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    inputs = capacity_inputs_from_profile(profile)
    answers = {q.id: str(profile[q.id]) for q in QUESTIONNAIRE_V2.questions}
    stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
    capacity = compute_capacity_ceiling(inputs)
    final = compute_final_tier(stated, capacity, inputs)
    suggested = {
        "answers": answers,
        "questionnaire_version": QUESTIONNAIRE_V2.version,
        "stated_score": stated.score,
        "stated_tier": final.stated_tier,
        "rule_table_version": CAPACITY_RULE_TABLE_V1.version,
        "capacity_ceiling": final.capacity_ceiling,
        "capacity_components": [asdict(component) for component in capacity.components],
        "final_tier": final.final_tier,
        "capped": final.capped,
        "binding_constraints": list(final.binding_constraints),
        "unlock_conditions": [asdict(condition) for condition in final.unlock_conditions],
    }
    context = {
        "buffer_coverage_months": str(inputs.buffer_coverage_months),
        "emi_to_income_ratio": str(inputs.emi_to_income_ratio),
        "income_stability": inputs.income_stability.value,
        "dependents_count": inputs.dependents_count,
        "total_life_cover_paise": inputs.total_life_cover_paise,
        "monthly_income_paise": inputs.monthly_income_paise,
        "cash_balance_paise": inputs.cash_balance_paise,
        "essential_monthly_expense_paise": inputs.essential_monthly_expense_paise,
        "total_monthly_emi_paise": inputs.total_monthly_emi_paise,
    }
    return suggested, context


def _format_money_from_message(message: str) -> int:
    match = re.search(r"\bRs\s+([\d,]+)", message)
    if match is None:
        raise ValueError("message contains no parseable rupee amount")
    return int(match.group(1).replace(",", ""))


def apply_unlock_condition(
    inputs: CapacityInputs,
    condition: dict[str, Any],
) -> tuple[CapacityInputs | None, str | None]:
    """Apply one literal user-facing unlock instruction to capacity inputs."""
    constraint = condition.get("constraint")
    message = str(condition.get("message", ""))
    if constraint == "buffer_months":
        match = re.search(r"Reach\s+([0-9.]+)\s+months", message)
        if match is None:
            return None, "unable to parse target buffer months"
        target_months = Decimal(match.group(1))
        target_cash = int(target_months * inputs.essential_monthly_expense_paise)
        return replace(
            inputs,
            buffer_coverage_months=target_months,
            cash_balance_paise=max(inputs.cash_balance_paise, target_cash),
        ), None
    if constraint == "emi_to_income_ratio":
        try:
            reduction_paise = _format_money_from_message(message) * 100
        except ValueError as error:
            return None, str(error)
        new_emi = max(0, inputs.total_monthly_emi_paise - reduction_paise)
        return replace(
            inputs,
            total_monthly_emi_paise=new_emi,
            emi_to_income_ratio=Decimal(new_emi) / Decimal(inputs.monthly_income_paise),
        ), None
    if constraint == "insurance_adequacy":
        try:
            increase_paise = _format_money_from_message(message) * 100
        except ValueError as error:
            return None, str(error)
        return replace(
            inputs,
            total_life_cover_paise=inputs.total_life_cover_paise + increase_paise,
        ), None
    if constraint == "income_stability":
        return replace(inputs, income_stability=IncomeStabilityValue.REGULAR), None
    return None, f"unsupported unlock constraint: {constraint!r}"


def _build_logged_records() -> list[dict[str, Any]]:
    database_path = Path(CONFIG["database_path"])
    if not database_path.is_file():
        return []
    uri = f"file:{database_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT timestamp, suggested_value, market_context "
            "FROM suggestion_event WHERE module_source = ? ORDER BY timestamp, event_id",
            ("risk_profile",),
        ).fetchall()
    records = []
    for index, row in enumerate(rows, start=1):
        records.append(
            {
                "record_id": f"logged-risk-profile-{index:04d}",
                "suggested_value": json.loads(row["suggested_value"] or "{}"),
                "market_context": json.loads(row["market_context"] or "{}"),
                "timestamp": row["timestamp"],
            }
        )
    return records


def _capacity_for_logged_context(context: dict[str, Any]) -> CapacityInputs:
    return _capacity_inputs_from_context(context)


def _analyze_replay_and_traces(
    cohort: list[dict[str, Any]],
    logged_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    replay_groups: dict[str, list[bool]] = {"synthetic_cohort": [], "logged_database": []}
    mismatch_rows: list[dict[str, Any]] = []
    gap_groups: dict[str, list[bool]] = {"synthetic_cohort": [], "logged_database": []}
    gap_rows: list[dict[str, Any]] = []
    unlock_rows: list[dict[str, Any]] = []
    cohort_scenarios: dict[str, dict[str, Any]] = {}
    synthetic_category_seen: set[str] = set()

    for index, profile in enumerate(cohort, start=1):
        suggested, context = _profile_decision(profile)
        record_id = str(profile.get("profile_id") or f"cohort-{index:05d}")
        event = make_explanation_event(record_id, suggested, context)
        trace = build_trace(event)
        _, replay_mismatches = compare_logged_decision(suggested, context)
        has_gap, gap_fields = _trace_completeness_gap(trace, replay_mismatches)
        gap_groups["synthetic_cohort"].append(has_gap)
        if has_gap:
            gap_rows.append(
                {
                    "dataset": "synthetic_cohort",
                    "record_id": record_id,
                    "missing_fields": ", ".join(gap_fields),
                }
            )

        mismatches = replay_mismatches
        replay_groups["synthetic_cohort"].append(not mismatches)
        if mismatches:
            mismatch_rows.append(
                {
                    "dataset": "synthetic_cohort",
                    "record_id": record_id,
                    "mismatch_fields": " | ".join(mismatches),
                }
            )

        _evaluate_unlocks(
            "synthetic_cohort",
            record_id,
            suggested,
            context,
            unlock_rows,
        )

        binding = tuple(sorted(suggested["binding_constraints"]))
        stratum = str(profile.get("stratum", ""))
        categories = []
        if suggested["capped"] and binding == ("emi_to_income_ratio",):
            categories.append("capped_emi_only")
        if not suggested["capped"] and stratum == "able_but_unwilling":
            categories.append("uncapped_able_but_unwilling")
        if suggested["capped"] and len(binding) > 1:
            categories.append("tied_constraints")
        if suggested["capped"] and binding == ("buffer_months",):
            categories.append("capped_buffer_only")
        if suggested["capped"] and binding == ("insurance_adequacy",):
            categories.append("capped_insurance_only")
        if not suggested["capped"] and stratum == "aligned":
            categories.append("uncapped_aligned")
        for category in categories:
            if category not in synthetic_category_seen:
                cohort_scenarios[category] = {
                    "profile": profile,
                    "suggested_value": suggested,
                    "market_context": context,
                    "trace": trace,
                }
                synthetic_category_seen.add(category)

    for record in logged_records:
        record_id = record["record_id"]
        suggested = record["suggested_value"]
        context = record["market_context"]
        event = make_explanation_event(
            record_id,
            suggested,
            context,
            record.get("timestamp"),
        )
        trace = build_trace(event)
        _, replay_mismatches = compare_logged_decision(suggested, context)
        has_gap, gap_fields = _trace_completeness_gap(trace, replay_mismatches)
        gap_groups["logged_database"].append(has_gap)
        if has_gap:
            gap_rows.append(
                {
                    "dataset": "logged_database",
                    "record_id": record_id,
                    "missing_fields": ", ".join(gap_fields),
                }
            )

        mismatches = replay_mismatches
        replay_groups["logged_database"].append(not mismatches)
        if mismatches:
            mismatch_rows.append(
                {
                    "dataset": "logged_database",
                    "record_id": record_id,
                    "mismatch_fields": " | ".join(mismatches),
                }
            )
        _evaluate_unlocks(
            "logged_database",
            record_id,
            suggested,
            context,
            unlock_rows,
        )

    replay_summary = []
    for group_index, (dataset, outcomes) in enumerate(replay_groups.items()):
        n = len(outcomes)
        mean, low, high = bootstrap_mean_ci(
            np.asarray(outcomes, dtype=float),
            int(CONFIG["bootstrap_seed"]) + group_index,
        )
        replay_summary.append(
            {
                "dataset": dataset,
                "traces": n,
                "matched": int(sum(outcomes)),
                "mismatched": int(n - sum(outcomes)),
                "match_rate": mean,
                "ci95_low": low,
                "ci95_high": high,
            }
        )

    completeness_summary = []
    for group_index, (dataset, outcomes) in enumerate(gap_groups.items()):
        n = len(outcomes)
        mean, low, high = bootstrap_mean_ci(
            np.asarray(outcomes, dtype=float),
            int(CONFIG["bootstrap_seed"]) + 10 + group_index,
        )
        completeness_summary.append(
            {
                "dataset": dataset,
                "traces": n,
                "gaps": int(sum(outcomes)),
                "complete": int(n - sum(outcomes)),
                "gap_share": mean,
                "ci95_low": low,
                "ci95_high": high,
            }
        )

    return replay_summary, mismatch_rows, completeness_summary, {
        "unlock_rows": unlock_rows,
        "gap_rows": gap_rows,
        "cohort_scenarios": cohort_scenarios,
    }


def _evaluate_unlocks(
    dataset: str,
    record_id: str,
    suggested: dict[str, Any],
    context: dict[str, Any],
    output_rows: list[dict[str, Any]],
) -> None:
    if not suggested.get("capped"):
        return
    try:
        inputs = _capacity_for_logged_context(context)
    except (ValueError, KeyError, TypeError) as error:
        output_rows.append(
            {
                "dataset": dataset,
                "record_id": record_id,
                "constraint": "missing_capacity_inputs",
                "promised_tier": suggested.get("stated_tier"),
                "ceiling_before": suggested.get("capacity_ceiling"),
                "ceiling_after": "",
                "valid": False,
                "reason": str(error),
                "instruction": "",
            }
        )
        return
    target_tier = int(suggested.get("stated_tier", 0))
    conditions = suggested.get("unlock_conditions") or []
    if not conditions:
        output_rows.append(
            {
                "dataset": dataset,
                "record_id": record_id,
                "constraint": "missing_unlock_conditions",
                "promised_tier": target_tier,
                "ceiling_before": suggested.get("capacity_ceiling"),
                "ceiling_after": "",
                "valid": False,
                "reason": "capped trace has no unlock condition",
                "instruction": "",
            }
        )
        return
    for condition in conditions:
        updated_inputs, error = apply_unlock_condition(inputs, condition)
        ceiling_after = ""
        emi_ratio_after = ""
        if updated_inputs is not None:
            ceiling_after = compute_capacity_ceiling(updated_inputs).ceiling
            if condition.get("constraint") == "emi_to_income_ratio":
                emi_ratio_after = float(updated_inputs.emi_to_income_ratio)
        valid = updated_inputs is not None and int(ceiling_after) >= target_tier
        instruction = str(condition.get("message", ""))
        if dataset == "logged_database":
            instruction = re.sub(r"\bRs\s+[\d,]+", "Rs [redacted]", instruction)
        output_rows.append(
            {
                "dataset": dataset,
                "record_id": record_id,
                "constraint": condition.get("constraint", ""),
                "promised_tier": target_tier,
                "ceiling_before": suggested.get("capacity_ceiling"),
                "ceiling_after": ceiling_after,
                "emi_ratio_after": emi_ratio_after,
                "valid": bool(valid),
                "reason": error or (
                    "capacity reached promised tier"
                    if valid
                    else "capacity ceiling remains below promised tier"
                ),
                "instruction": instruction,
            }
        )


def _unlock_summaries(unlock_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    group_keys = sorted(
        {(str(row["dataset"]), str(row["constraint"])) for row in unlock_rows}
    )
    summaries = []
    for index, (dataset, constraint) in enumerate(group_keys):
        rows = [
            row
            for row in unlock_rows
            if row["dataset"] == dataset and row["constraint"] == constraint
        ]
        values = np.asarray([bool(row["valid"]) for row in rows], dtype=float)
        mean, low, high = bootstrap_mean_ci(
            values,
            int(CONFIG["bootstrap_seed"]) + 100 + index,
        )
        summaries.append(
            {
                "dataset": dataset,
                "constraint": constraint,
                "conditions": len(rows),
                "valid": int(values.sum()),
                "failed": int(len(rows) - values.sum()),
                "valid_share": mean,
                "ci95_low": low,
                "ci95_high": high,
            }
        )
    return summaries


def _emi_boundary_summary(unlock_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    emi_rows = [row for row in unlock_rows if row["constraint"] == "emi_to_income_ratio"]
    groups = sorted(
        {(row["dataset"], int(row["promised_tier"])) for row in emi_rows}
    )
    summaries = []
    for dataset, tier in groups:
        rows = [
            row
            for row in emi_rows
            if row["dataset"] == dataset and int(row["promised_tier"]) == tier
        ]
        band = next(band for band in CAPACITY_RULE_TABLE_V1.emi_to_income_bands if band.ceiling == tier)
        threshold = Decimal(str(band.max_value)) if band.max_value is not None else None
        at_boundary = [
            row
            for row in rows
            if threshold is not None
            and row.get("emi_ratio_after") != ""
            and Decimal(str(row["emi_ratio_after"])) == threshold
        ]
        at_or_above_boundary = [
            row
            for row in rows
            if threshold is not None
            and row.get("emi_ratio_after") != ""
            and Decimal(str(row["emi_ratio_after"])) >= threshold
        ]
        boundary_share, boundary_low, boundary_high = bootstrap_mean_ci(
            np.asarray(
                [
                    threshold is not None
                    and row.get("emi_ratio_after") != ""
                    and Decimal(str(row["emi_ratio_after"])) == threshold
                    for row in rows
                ],
                dtype=float,
            ),
            int(CONFIG["bootstrap_seed"]) + len(summaries) + 300,
        )
        failed_boundary_share, failed_boundary_low, failed_boundary_high = bootstrap_mean_ci(
            np.asarray([not row["valid"] for row in at_boundary], dtype=float),
            int(CONFIG["bootstrap_seed"]) + len(summaries) + 400,
        )
        at_or_above_share, at_or_above_low, at_or_above_high = bootstrap_mean_ci(
            np.asarray(
                [
                    threshold is not None
                    and row.get("emi_ratio_after") != ""
                    and Decimal(str(row["emi_ratio_after"])) >= threshold
                    for row in rows
                ],
                dtype=float,
            ),
            int(CONFIG["bootstrap_seed"]) + len(summaries) + 500,
        )
        failed_at_or_above = sum(not row["valid"] for row in at_or_above_boundary)
        failed_at_or_above_share, failed_at_or_above_low, failed_at_or_above_high = bootstrap_mean_ci(
            np.asarray([not row["valid"] for row in at_or_above_boundary], dtype=float),
            int(CONFIG["bootstrap_seed"]) + len(summaries) + 600,
        )
        summaries.append(
            {
                "dataset": dataset,
                "promised_tier": tier,
                "conditions": len(rows),
                "exclusive_upper_threshold": float(threshold) if threshold is not None else "",
                "at_exclusive_threshold": len(at_boundary),
                "above_exclusive_threshold": sum(
                    threshold is not None
                    and row.get("emi_ratio_after") != ""
                    and Decimal(str(row["emi_ratio_after"])) > threshold
                    for row in rows
                ),
                "at_threshold_share": boundary_share,
                "at_threshold_ci95_low": boundary_low,
                "at_threshold_ci95_high": boundary_high,
                "failed_at_threshold": sum(not row["valid"] for row in at_boundary),
                "failed_at_threshold_share": failed_boundary_share,
                "failed_threshold_ci95_low": failed_boundary_low,
                "failed_threshold_ci95_high": failed_boundary_high,
                "at_or_above_exclusive_threshold": len(at_or_above_boundary),
                "at_or_above_threshold_share": at_or_above_share,
                "at_or_above_ci95_low": at_or_above_low,
                "at_or_above_ci95_high": at_or_above_high,
                "failed_at_or_above_threshold": failed_at_or_above,
                "failed_at_or_above_share": failed_at_or_above_share,
                "failed_at_or_above_ci95_low": failed_at_or_above_low,
                "failed_at_or_above_ci95_high": failed_at_or_above_high,
                "failed_total": sum(not row["valid"] for row in rows),
            }
        )
    return summaries


def _suspect_boundary_case() -> dict[str, Any]:
    case = CONFIG["suspect_emi_boundary_case"]
    income_paise = int(case["monthly_income_rupees"]) * 100
    emi_paise = int(case["monthly_emi_rupees"]) * 100
    essential_paise = int(case["essential_expense_rupees"]) * 100
    inputs = CapacityInputs(
        buffer_coverage_months=Decimal(str(case["cash_buffer_months"])),
        emi_to_income_ratio=Decimal(emi_paise) / Decimal(income_paise),
        income_stability=IncomeStabilityValue.REGULAR,
        dependents_count=0,
        total_life_cover_paise=0,
        monthly_income_paise=income_paise,
        cash_balance_paise=essential_paise * int(case["cash_buffer_months"]),
        essential_monthly_expense_paise=essential_paise,
        total_monthly_emi_paise=emi_paise,
    )
    answers = {q.id: q.options[-1].value for q in QUESTIONNAIRE_V2.questions}
    stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
    capacity = compute_capacity_ceiling(inputs)
    final = compute_final_tier(stated, capacity, inputs)
    condition = next(
        condition
        for condition in final.unlock_conditions
        if condition.constraint == "emi_to_income_ratio"
    )
    if _format_money_from_message(condition.message) != int(case["requested_reduction_rupees"]):
        raise ValueError("production unlock amount differs from the configured task boundary case")
    exact_case_condition = asdict(condition)
    updated, error = apply_unlock_condition(inputs, exact_case_condition)
    if updated is None:
        raise ValueError(f"unable to apply configured boundary case: {error}")
    capacity_after = compute_capacity_ceiling(updated).ceiling
    return {
        "monthly_income_rupees": int(case["monthly_income_rupees"]),
        "monthly_emi_rupees": int(case["monthly_emi_rupees"]),
        "requested_reduction_rupees": int(case["requested_reduction_rupees"]),
        "emi_ratio_before": float(inputs.emi_to_income_ratio),
        "displayed_instruction": exact_case_condition["message"],
        "promised_tier": stated.tier,
        "capacity_ceiling_before": capacity.ceiling,
        "emi_ratio_after": float(updated.emi_to_income_ratio),
        "capacity_ceiling_after": capacity_after,
        "unlock_valid": capacity_after >= stated.tier,
        "upper_band_boundary": float(
            next(
                band.max_value
                for band in CAPACITY_RULE_TABLE_V1.emi_to_income_bands
                if band.ceiling == stated.tier
            )
        ),
    }


def _load_model_data() -> dict[str, dict[str, Any]]:
    """Rebuild the stratified split using generate_results.py's split recipe."""
    rows = load_training_rows()
    y = np.asarray(
        [compute_stated_tier(row, QUESTIONNAIRE_V2).tier for row in rows],
        dtype=int,
    )
    data: dict[str, dict[str, Any]] = {}
    for feature_set, feature_names in FEATURE_SETS.items():
        X = np.asarray(
            [
                [
                    QUESTIONNAIRE_V2.option_points(feature, answers[feature])
                    for feature in feature_names
                ]
                for answers in rows
            ],
            dtype=float,
        )
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=float(CONFIG["test_split_fraction"]),
            random_state=int(CONFIG["test_split_seed"]),
            stratify=y,
        )
        data[feature_set] = {
            "X_train": X_train,
            "X_test": X_test,
            "y_train": y_train,
            "y_test": y_test,
            "feature_names": feature_names,
        }
    return data


def _bootstrap_rank_stability(values: np.ndarray, seed: int) -> tuple[float, float, float]:
    baseline = np.mean(np.abs(values), axis=0)
    baseline_ranks = stats.rankdata(-baseline, method="average")
    rng = np.random.default_rng(seed)
    correlations = np.empty(int(CONFIG["stability_replicates"]), dtype=float)
    for replicate in range(len(correlations)):
        sample = rng.integers(0, len(values), size=len(values))
        ranks = stats.rankdata(-np.mean(np.abs(values[sample]), axis=0), method="average")
        correlations[replicate] = stats.spearmanr(baseline_ranks, ranks).statistic
    tail = (1.0 - float(CONFIG["ci_level"])) / 2.0
    low, high = np.quantile(correlations, [tail, 1.0 - tail])
    return float(np.mean(correlations)), float(low), float(high)


def _run_shap_analysis() -> dict[str, Any]:
    data = _load_model_data()
    model_specs = (
        ("full_7items", Path(CONFIG["full_model_path"])),
        ("reduced_4items", Path(CONFIG["reduced_model_path"])),
    )
    additivity_rows: list[dict[str, Any]] = []
    deletion_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    warning_messages: list[str] = []
    plot_data: dict[str, dict[str, Any]] = {}

    for model_index, (feature_set, model_path) in enumerate(model_specs):
        if not model_path.is_file():
            raise FileNotFoundError(f"production model not found: {model_path}")
        split = data[feature_set]
        X_train = split["X_train"]
        X_test = split["X_test"]
        feature_names = split["feature_names"]
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            model = (
                load_versioned_model(model_path)
                if model_path.parent.name == "v2"
                else joblib.load(model_path)
            )
        warning_messages.extend(str(item.message) for item in captured)
        background = shap.sample(
            X_train,
            min(int(CONFIG["shap_background_size"]), len(X_train)),
            random_state=int(CONFIG["shap_background_seed"]),
        )
        explainer = shap.TreeExplainer(
            model,
            data=background,
            model_output="probability",
            feature_perturbation="interventional",
        )
        explanation = explainer(X_test)
        shap_values = np.asarray(explanation.values, dtype=float)
        base_values = np.asarray(explanation.base_values, dtype=float)
        if shap_values.ndim != 3 or base_values.ndim != 2:
            raise ValueError(
                f"unexpected SHAP shapes for {feature_set}: "
                f"values={shap_values.shape}, base={base_values.shape}"
            )

        predicted_probabilities = model.predict_proba(X_test)
        predicted_indices = np.argmax(predicted_probabilities, axis=1)
        row_indices = np.arange(len(X_test))
        additive_estimates = (
            base_values[row_indices, predicted_indices]
            + shap_values[row_indices, :, predicted_indices].sum(axis=1)
        )
        selected_probabilities = predicted_probabilities[row_indices, predicted_indices]
        additive_errors = np.abs(additive_estimates - selected_probabilities)
        mean_error, error_low, error_high = bootstrap_mean_ci(
            additive_errors,
            int(CONFIG["bootstrap_seed"]) + model_index,
        )
        match_values = (
            additive_errors <= float(CONFIG["shap_additivity_tolerance"])
        ).astype(float)
        match_share, match_low, match_high = bootstrap_mean_ci(
            match_values,
            int(CONFIG["bootstrap_seed"]) + 10 + model_index,
        )
        additivity_rows.append(
            {
                "model": feature_set,
                "n_test": len(X_test),
                "tolerance": float(CONFIG["shap_additivity_tolerance"]),
                "mean_absolute_error": mean_error,
                "mean_error_ci95_low": error_low,
                "mean_error_ci95_high": error_high,
                "maximum_absolute_error": float(np.max(additive_errors)),
                "within_tolerance": int(match_values.sum()),
                "within_tolerance_share": match_share,
                "share_ci95_low": match_low,
                "share_ci95_high": match_high,
            }
        )

        row_shap = shap_values[row_indices, :, predicted_indices]
        absolute_row_shap = np.abs(row_shap)
        mean_abs = absolute_row_shap.mean(axis=0)
        rng = np.random.default_rng(int(CONFIG["stability_seed"]) + model_index)
        stability_boot = np.empty(
            (int(CONFIG["stability_replicates"]), len(feature_names)),
            dtype=float,
        )
        for replicate in range(len(stability_boot)):
            sample = rng.integers(0, len(shap_values), size=len(shap_values))
            stability_boot[replicate] = absolute_row_shap[sample].mean(axis=0)
        tail = (1.0 - float(CONFIG["ci_level"])) / 2.0
        lower = np.quantile(stability_boot, tail, axis=0)
        upper = np.quantile(stability_boot, 1.0 - tail, axis=0)
        for feature_index, feature_name in enumerate(feature_names):
            importance_rows.append(
                {
                    "model": feature_set,
                    "feature": feature_name,
                    "feature_label": FEATURE_LABELS[feature_name],
                    "mean_absolute_shap": float(mean_abs[feature_index]),
                    "ci95_low": float(lower[feature_index]),
                    "ci95_high": float(upper[feature_index]),
                }
            )
        stability_mean, stability_low, stability_high = _bootstrap_rank_stability(
            shap_values[row_indices, :, predicted_indices],
            int(CONFIG["stability_seed"]) + 20 + model_index,
        )
        stability_rows.append(
            {
                "model": feature_set,
                "n_test": len(X_test),
                "rank_spearman_mean": stability_mean,
                "ci95_low": stability_low,
                "ci95_high": stability_high,
                "bootstrap_replicates": int(CONFIG["stability_replicates"]),
            }
        )

        k = min(int(CONFIG["deletion_top_k"]), len(feature_names))
        medians = np.median(X_train, axis=0)
        drops = np.empty_like(absolute_row_shap, dtype=float)
        for feature_index in range(len(feature_names)):
            perturbed = X_test.copy()
            perturbed[:, feature_index] = medians[feature_index]
            perturbed_probabilities = model.predict_proba(perturbed)
            drops[:, feature_index] = (
                selected_probabilities
                - perturbed_probabilities[row_indices, predicted_indices]
            )
        top_indices = np.argsort(-absolute_row_shap, axis=1)[:, :k]
        low_indices = np.argsort(absolute_row_shap, axis=1)[:, :k]
        top_drops = np.take_along_axis(drops, top_indices, axis=1).mean(axis=1)
        low_drops = np.take_along_axis(drops, low_indices, axis=1).mean(axis=1)
        random_draw_values = np.empty(
            (len(X_test), int(CONFIG["random_feature_draws"])),
            dtype=float,
        )
        random_rng = np.random.default_rng(int(CONFIG["bootstrap_seed"]) + 50 + model_index)
        for row_index in range(len(X_test)):
            for draw_index in range(int(CONFIG["random_feature_draws"])):
                random_features = random_rng.choice(len(feature_names), size=k, replace=False)
                random_draw_values[row_index, draw_index] = drops[row_index, random_features].mean()
        random_drops = random_draw_values.mean(axis=1)
        group_values = {
            f"top_{k}_shap": top_drops,
            "random_k": random_drops,
            f"lowest_{k}_shap": low_drops,
        }
        for group_index, (method, values) in enumerate(group_values.items()):
            mean, low, high = bootstrap_mean_ci(
                values,
                int(CONFIG["bootstrap_seed"]) + 100 + model_index * 10 + group_index,
            )
            deletion_rows.append(
                {
                    "model": feature_set,
                    "method": method,
                    "features_evaluated_per_profile": k,
                    "mean_predicted_class_probability_drop": mean,
                    "ci95_low": low,
                    "ci95_high": high,
                }
            )
        for contrast_index, (name, other) in enumerate(
            (("top_minus_random", random_drops), ("top_minus_lowest", low_drops))
        ):
            mean, low, high = bootstrap_mean_ci(
                top_drops - other,
                int(CONFIG["bootstrap_seed"]) + 150 + model_index * 10 + contrast_index,
            )
            comparison_rows.append(
                {
                    "model": feature_set,
                    "comparison": name,
                    "mean_paired_drop_difference": mean,
                    "ci95_low": low,
                    "ci95_high": high,
                }
            )
        plot_data[feature_set] = {
            "deletion": group_values,
            "importance": mean_abs,
            "feature_names": feature_names,
        }

    warning_messages = list(dict.fromkeys(warning_messages))
    return {
        "additivity_rows": additivity_rows,
        "deletion_rows": deletion_rows,
        "comparison_rows": comparison_rows,
        "importance_rows": importance_rows,
        "stability_rows": stability_rows,
        "warning_messages": warning_messages,
        "plot_data": plot_data,
        "split_sizes": {
            feature_set: {
                "train": len(split["X_train"]),
                "test": len(split["X_test"]),
            }
            for feature_set, split in data.items()
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not rows:
        return ["No rows."]
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, separator]
    for row in rows:
        cells = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, (float, np.floating)):
                cell = "N/A" if not math.isfinite(float(value)) else f"{float(value):.4f}"
            elif isinstance(value, bool):
                cell = str(value)
            else:
                cell = str(value)
            cells.append(cell.replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _write_faithfulness_plot(
    results_dir: Path,
    plot_data: dict[str, dict[str, Any]],
) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    k = min(
        int(CONFIG["deletion_top_k"]),
        max(len(item["feature_names"]) for item in plot_data.values()),
    )
    method_order = (f"top_{k}_shap", "random_k", f"lowest_{k}_shap")
    method_labels = ("Top SHAP", "Random", "Lowest SHAP")
    x = np.arange(len(method_order))
    width = 0.34
    for model_index, (model, values) in enumerate(plot_data.items()):
        offset = (model_index - 0.5) * width
        means = []
        lows = []
        highs = []
        for method in method_order:
            vals = values["deletion"][method]
            mean = float(np.mean(vals))
            _, low, high = bootstrap_mean_ci(
                vals,
                int(CONFIG["bootstrap_seed"]) + 200 + model_index * 10 + len(means),
            )
            means.append(mean)
            lows.append(mean - low)
            highs.append(high - mean)
        axes[0].bar(
            x + offset,
            means,
            width,
            yerr=np.asarray([lows, highs]),
            capsize=3,
            label=model.replace("_", " "),
            color=("#3478b8", "#e2944a")[model_index],
        )
    axes[0].axhline(0, color="#555555", linewidth=0.8)
    axes[0].set_xticks(x, method_labels)
    axes[0].set_ylabel("Mean predicted-class probability drop")
    axes[0].set_title("Deletion test (95% bootstrap CIs)")
    axes[0].legend(frameon=False)

    for model, values in plot_data.items():
        features = values["feature_names"]
        order = np.argsort(values["importance"])
        axes[1].plot(
            values["importance"][order],
            np.arange(len(features)),
            marker="o",
            label=model.replace("_", " "),
        )
        if model == "full_7items":
            labels = [FEATURE_LABELS[features[index]] for index in order]
            axes[1].set_yticks(np.arange(len(features)), labels)
    axes[1].set_xlabel("Mean absolute SHAP value")
    axes[1].set_title("Global feature attribution")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    output = results_dir / "shap_faithfulness.png"
    fig.savefig(output, dpi=int(CONFIG["plot_dpi"]), bbox_inches="tight")
    plt.close(fig)
    return output


def _scenario_label(category: str) -> str:
    return {
        "capped_emi_only": "A capped profile with EMI as the sole binding component",
        "uncapped_able_but_unwilling": "An uncapped able-but-unwilling profile",
        "tied_constraints": "A capped profile with tied binding components",
        "capped_buffer_only": "A capped profile with emergency buffer as the sole binding component",
        "capped_insurance_only": "A capped profile with insurance as the sole binding component",
        "uncapped_aligned": "An uncapped aligned profile",
    }[category]


def _write_user_study_kit(
    scenarios: dict[str, dict[str, Any]],
) -> list[Path]:
    study_dir = Path(CONFIG["user_study_dir"])
    cards_dir = study_dir / "scenario_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    scenario_rows = []
    for index, category in enumerate(CONFIG["scenario_categories"], start=1):
        if category not in scenarios:
            raise ValueError(f"no saved-cohort example found for scenario {category!r}")
        scenario = scenarios[category]
        suggested = scenario["suggested_value"]
        trace = scenario["trace"]
        scenario_id = f"S{index:02d}"
        scenario_rows.append(
            {
                "scenario_id": scenario_id,
                "category": category,
                "label": _scenario_label(category),
                "stated_tier": suggested["stated_tier"],
                "capacity_ceiling": suggested["capacity_ceiling"],
                "final_tier": suggested["final_tier"],
                "binding_constraints": suggested["binding_constraints"],
                "unlock_conditions": suggested["unlock_conditions"],
            }
        )
        card_lines = [
            f"# {scenario_id}: {_scenario_label(category)}",
            "",
            "This is a fictional example produced by the saved synthetic cohort and the production risk-profile and transparency functions. It does not describe a real person.",
            "",
            "## Explanation shown",
            "",
            trace.headline,
            "",
        ]
        for section in trace.sections:
            if section.summary:
                card_lines.extend([f"**{section.title}:** {section.summary}", ""])
        card_lines.extend(
            [
                "## Decision facts",
                "",
                f"- Stated tier: {suggested['stated_tier']}.",
                f"- Capacity ceiling: {suggested['capacity_ceiling']}.",
                f"- Final tier: {suggested['final_tier']}.",
                f"- Binding components: {', '.join(suggested['binding_constraints']) or 'none'}.",
            ]
        )
        if suggested["unlock_conditions"]:
            card_lines.append("- Suggested changes:")
            card_lines.extend(
                f"  - {condition['message']}" for condition in suggested["unlock_conditions"]
            )
        else:
            card_lines.append("- No capacity cap or unlock condition was returned.")
        card_lines.extend(
            [
                "",
                "The example is intentionally anonymized; the profile identifier is not included in the card.",
                "",
            ]
        )
        card_path = cards_dir / f"{scenario_id.lower()}_{category}.md"
        card_path.write_text("\n".join(card_lines), encoding="utf-8")
        created.append(card_path)

    protocol = study_dir / "protocol.md"
    protocol.write_text(
        "\n".join(
            [
                "# Explanation faithfulness user-study protocol",
                "",
                "## Purpose",
                "",
                "Collect user ratings of explanation clarity, trust, and perceived fairness, and check whether participants understand the stated tier, capacity ceiling, binding component, and suggested action. This protocol does not assert that any explanation is correct or fair.",
                "",
                "## Materials and procedure",
                "",
                "Present the six scenario cards in a randomized order. Keep the card visible while the participant answers its three rating items and comprehension question. Record responses using `response_template.csv`; do not collect names, account identifiers, or financial information. The cards describe synthetic profiles generated by the production pipeline.",
                "",
                "## Consent",
                "",
                "Participation is voluntary. The participant may skip any question or stop at any time without penalty. Responses will be recorded using a participant code rather than a name and used only to evaluate these example explanations. No real financial account data is requested. By continuing, the participant confirms they understand this information and consent to take part.",
                "",
                "## Response scale and scoring",
                "",
                "For each statement, select one response on the 5-point scale: 1 = Strongly disagree, 2 = Disagree, 3 = Neither agree nor disagree, 4 = Agree, 5 = Strongly agree. Comprehension responses are free text and should be scored against the answer key in `questionnaire.md`.",
                "",
                "## Safeguards and limitations",
                "",
                "Do not interpret these synthetic scenarios as personal financial advice. Keep participant responses separate from the machine-generated analysis outputs. This kit is a protocol template and contains no participant data or study results.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    created.append(protocol)

    questionnaire_lines = [
        "# User questionnaire and comprehension answer key",
        "",
        "For each scenario, rate each statement using the 5-point scale defined in `protocol.md`.",
        "",
        "| Scenario | Clarity | Trust | Perceived fairness | Comprehension question |",
        "|---|---|---|---|---|",
    ]
    answer_lines = [
        "",
        "## Comprehension answer key",
        "",
        "Accept a response that identifies the scenario's final tier and the listed binding component(s), or states that the profile was not capped when applicable.",
        "",
        "| Scenario | Expected answer |",
        "|---|---|",
    ]
    for scenario in scenario_rows:
        expected = (
            f"Final tier {scenario['final_tier']}; binding component(s): "
            f"{', '.join(scenario['binding_constraints']) or 'none'}."
        )
        questionnaire_lines.append(
            f"| {scenario['scenario_id']} | The explanation is easy to understand. | "
            "I trust this recommendation. | This decision treats the stated preference fairly. | "
            "What is the final tier, and which component(s), if any, set the capacity ceiling? |"
        )
        answer_lines.append(f"| {scenario['scenario_id']} | {expected} |")
    questionnaire_lines.extend(answer_lines)
    questionnaire = study_dir / "questionnaire.md"
    questionnaire.write_text("\n".join(questionnaire_lines) + "\n", encoding="utf-8")
    created.append(questionnaire)

    response_template = study_dir / "response_template.csv"
    with response_template.open("w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "participant_code",
            "scenario_id",
            "clarity_1_to_5",
            "trust_1_to_5",
            "fairness_1_to_5",
            "comprehension_response",
            "optional_comment",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for scenario in scenario_rows:
            writer.writerow(
                {
                    "participant_code": "",
                    "scenario_id": scenario["scenario_id"],
                    "clarity_1_to_5": "",
                    "trust_1_to_5": "",
                    "fairness_1_to_5": "",
                    "comprehension_response": "",
                    "optional_comment": "",
                }
            )
    created.append(response_template)
    return created


def _write_results_report(
    report_path: Path,
    replay_summary: list[dict[str, Any]],
    mismatch_rows: list[dict[str, Any]],
    unlock_summary: list[dict[str, Any]],
    emi_boundary_summary: list[dict[str, Any]],
    suspect_case: dict[str, Any],
    unlock_failures: list[dict[str, Any]],
    completeness_summary: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    shap_results: dict[str, Any],
    versions: dict[str, str],
) -> None:
    additivity = shap_results["additivity_rows"]
    deletion = shap_results["deletion_rows"]
    comparisons = shap_results["comparison_rows"]
    importance = shap_results["importance_rows"]
    stability = shap_results["stability_rows"]
    lines = [
        "# Risk-explanation faithfulness checks",
        "",
        "## Part A: rule-trace replay and unlock validity",
        "",
        "Replay fidelity uses only the saved questionnaire answers and objective capacity inputs. Synthetic-cohort traces are generated from the saved cohort with the production functions; database rows are restricted to `suggestion_event.module_source = risk_profile`. Intervals are percentile bootstrap 95% confidence intervals.",
        "",
        "### Replay fidelity",
        "",
        *_markdown_table(
            replay_summary,
            [
                ("dataset", "Dataset"),
                ("traces", "Traces"),
                ("matched", "Matched"),
                ("mismatched", "Mismatched"),
                ("match_rate", "Match rate"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
            ],
        ),
        "",
        "All replay mismatches:",
        "",
        *_markdown_table(
            mismatch_rows,
            [
                ("dataset", "Dataset"),
                ("record_id", "Record"),
                ("mismatch_fields", "Mismatch details"),
            ],
        ),
        "",
        "### Unlock-condition validity",
        "",
        "Each unlock action is applied independently. Thus a single action for one tied binding component is not combined with other simultaneous unlock actions. Success means the recomputed production capacity ceiling reaches the stated willingness tier.",
        "",
        *_markdown_table(
            unlock_summary,
            [
                ("dataset", "Dataset"),
                ("constraint", "Component"),
                ("conditions", "Conditions"),
                ("valid", "Valid"),
                ("failed", "Failed"),
                ("valid_share", "Valid share"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
            ],
        ),
        "",
        "EMI outcomes at each promised tier's exclusive upper threshold:",
        "",
        "Production capacity bands use an exclusive upper bound. The table distinguishes ratios exactly at that boundary from ratios above it after the displayed whole-rupee reduction.",
        "",
        *_markdown_table(
            emi_boundary_summary,
            [
                ("dataset", "Dataset"),
                ("promised_tier", "Promised tier"),
                ("conditions", "Conditions"),
                ("exclusive_upper_threshold", "Exclusive upper ratio"),
                ("at_exclusive_threshold", "At boundary"),
                ("above_exclusive_threshold", "Above boundary"),
                ("at_threshold_share", "Boundary share"),
                ("at_threshold_ci95_low", "Boundary CI low"),
                ("at_threshold_ci95_high", "Boundary CI high"),
                ("failed_at_threshold", "Failed at boundary"),
                ("failed_at_threshold_share", "Failure share at boundary"),
                ("failed_threshold_ci95_low", "Failure CI low"),
                ("failed_threshold_ci95_high", "Failure CI high"),
                ("at_or_above_exclusive_threshold", "At or above boundary"),
                ("at_or_above_threshold_share", "At/above share"),
                ("at_or_above_ci95_low", "At/above CI low"),
                ("at_or_above_ci95_high", "At/above CI high"),
                ("failed_at_or_above_threshold", "Failures at/above"),
                ("failed_at_or_above_share", "Failure share at/above"),
                ("failed_at_or_above_ci95_low", "Failure CI low"),
                ("failed_at_or_above_ci95_high", "Failure CI high"),
                ("failed_total", "Failed total"),
            ],
        ),
        "",
        "Configured boundary case supplied in the task prompt, rerun through production risk functions:",
        "",
        *_markdown_table(
            [suspect_case],
            [
                ("monthly_income_rupees", "Monthly income (Rs)"),
                ("monthly_emi_rupees", "Monthly EMI (Rs)"),
                ("requested_reduction_rupees", "Displayed reduction (Rs)"),
                ("emi_ratio_before", "EMI ratio before"),
                ("emi_ratio_after", "EMI ratio after"),
                ("promised_tier", "Promised tier"),
                ("capacity_ceiling_before", "Ceiling before"),
                ("capacity_ceiling_after", "Ceiling after"),
                ("upper_band_boundary", "Exclusive boundary"),
                ("displayed_instruction", "Displayed instruction"),
                ("unlock_valid", "Unlock valid"),
            ],
        ),
        "",
        "All failing unlock cases:",
        "",
        *_markdown_table(
            unlock_failures,
            [
                ("dataset", "Dataset"),
                ("record_id", "Record"),
                ("constraint", "Component"),
                ("promised_tier", "Promised tier"),
                ("ceiling_before", "Ceiling before"),
                ("ceiling_after", "Ceiling after"),
                ("emi_ratio_after", "EMI ratio after"),
                ("reason", "Failure reason"),
                ("instruction", "Displayed instruction"),
            ],
        ),
        "",
        "### Transparency completeness",
        "",
        *_markdown_table(
            completeness_summary,
            [
                ("dataset", "Dataset"),
                ("traces", "Traces"),
                ("gaps", "Gaps flagged"),
                ("complete", "Complete"),
                ("gap_share", "Gap share"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
            ],
        ),
        "",
        "All traces with missing fields:",
        "",
        *_markdown_table(
            gap_rows,
            [
                ("dataset", "Dataset"),
                ("record_id", "Record"),
                ("missing_fields", "Missing fields flagged by transparency"),
            ],
        ),
        "",
        "## Part B: SHAP faithfulness for production Random Forests",
        "",
        f"Both models use the stratified held-out split rebuilt with test fraction {CONFIG['test_split_fraction']} and seed {CONFIG['test_split_seed']}. SHAP explains predicted-class probability with interventional tree SHAP and the configured training-background sample. Additivity tolerance is {CONFIG['shap_additivity_tolerance']}.",
        "",
        "### Additivity",
        "",
        *_markdown_table(
            [
                {
                    "model": model,
                    "train_rows": sizes["train"],
                    "test_rows": sizes["test"],
                }
                for model, sizes in shap_results["split_sizes"].items()
            ],
            [
                ("model", "Model"),
                ("train_rows", "Training rows"),
                ("test_rows", "Test rows"),
            ],
        ),
        "",
        *_markdown_table(
            additivity,
            [
                ("model", "Model"),
                ("n_test", "Test rows"),
                ("tolerance", "Tolerance"),
                ("mean_absolute_error", "Mean abs. error"),
                ("mean_error_ci95_low", "Mean error CI low"),
                ("mean_error_ci95_high", "Mean error CI high"),
                ("maximum_absolute_error", "Max abs. error"),
                ("within_tolerance", "Within tolerance"),
                ("within_tolerance_share", "Share within tolerance"),
                ("share_ci95_low", "Share CI low"),
                ("share_ci95_high", "Share CI high"),
            ],
        ),
        "",
        "### Deletion test",
        "",
        "For each test row, each selected feature is individually replaced by its training-set median. Probability drop is measured for the original predicted class. Random-feature controls average the configured number of random k-feature draws.",
        "",
        *_markdown_table(
            deletion,
            [
                ("model", "Model"),
                ("method", "Feature group"),
                ("features_evaluated_per_profile", "Features evaluated per profile"),
                ("mean_predicted_class_probability_drop", "Mean probability drop"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
            ],
        ),
        "",
        "Paired bootstrap contrasts, top-|SHAP| group minus the comparison group:",
        "",
        *_markdown_table(
            comparisons,
            [
                ("model", "Model"),
                ("comparison", "Comparison"),
                ("mean_paired_drop_difference", "Mean difference"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
            ],
        ),
        "",
        "### Global feature attribution",
        "",
        *_markdown_table(
            importance,
            [
                ("model", "Model"),
                ("feature_label", "Feature"),
                ("mean_absolute_shap", "Mean absolute SHAP"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
            ],
        ),
        "",
        "### SHAP rank stability",
        "",
        "Feature ranks are based on mean absolute predicted-class SHAP values across the test set. The stability interval resamples test rows and correlates each resampled feature ranking with the full-test ranking.",
        "",
        *_markdown_table(
            stability,
            [
                ("model", "Model"),
                ("n_test", "Test rows"),
                ("rank_spearman_mean", "Mean rank correlation"),
                ("ci95_low", "CI low"),
                ("ci95_high", "CI high"),
                ("bootstrap_replicates", "Bootstrap replicates"),
            ],
        ),
        "",
        "![SHAP deletion and feature attribution](./shap_faithfulness.png)",
        "",
        "## Part C: user-study kit",
        "",
        "The generated protocol and scenario cards are under `../user_study/`. Cards are based on saved synthetic cohort profiles processed by the production pipeline and transparency builder. The kit contains a protocol and consent text, six cards, a questionnaire with answer key, and a blank CSV response template; no participant responses are included.",
        "",
        "## Assumptions and threats to validity",
        "",
        "- Replay uses the logged questionnaire version, answers, and objective input fields; profiles lacking replay inputs are counted as mismatches that could not be replayed.",
        "- Capacity rules are recomputed with the current production V1 capacity table. Historical events from another rule-table version may therefore not replay identically.",
        "- Unlock actions are interpreted from the displayed message and tested one at a time; simultaneous tied conditions are not applied jointly.",
        "- Monetary unlock messages display whole rupees. When the arithmetic difference includes paise, the displayed reduction can leave the recomputed EMI ratio at or above the exclusive tier boundary.",
        "- A recommendation's stated tier is used as the promised unlock ceiling because the production explanation supplies no separate promised-tier field.",
        "- SHAP background data is a seeded sample of the training fold. Results depend on this background, the fixed production model artifacts, mapped questionnaire values, and held-out split.",
        "- Replacing a feature with its training median is a perturbation, not a realistic user intervention; correlated questionnaire responses may become implausible.",
        "- Deletion effects describe changes in the model's predicted-class probability, not changes in observed user outcomes or causal effects.",
        "- Bootstrap intervals quantify resampling uncertainty on these samples; they do not address dataset representativeness or model-artifact version compatibility.",
        "- Study cards are synthetic vignettes. The study kit does not contain evidence from participants.",
        "",
        "## Software versions",
        "",
        *_markdown_table(
            [{"component": key, "version": value} for key, value in versions.items()],
            [("component", "Component"), ("version", "Version")],
        ),
    ]
    if shap_results["warning_messages"]:
        lines.extend(["", "## Model-loading warnings", ""])
        lines.extend(f"- {warning}" for warning in shap_results["warning_messages"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_analysis(model_version: str | None = None) -> dict[str, Path]:
    if model_version not in (None, "old", "v2"):
        raise ValueError(f"unsupported model version selection: {model_version!r}")
    if model_version is not None:
        results_base = ROOT / "research_artifacts" / "experiments" / "results_v2"
        output_dir = results_base / f"model_faithfulness_{model_version}"
        if output_dir.exists():
            raise FileExistsError(
                f"refusing to overwrite previous model-faithfulness outputs: {output_dir}"
            )
        CONFIG["results_dir"] = output_dir
        CONFIG["user_study_dir"] = output_dir / "user_study"
        if model_version == "v2":
            model_dir = BACKEND_DIR / "app" / "ml_models" / "v2"
            CONFIG["full_model_path"] = model_dir / "risk_tier_rf.pkl"
            CONFIG["reduced_model_path"] = model_dir / "risk_tier_rf_reduced_4items.pkl"
        else:
            CONFIG["full_model_path"] = BACKEND_DIR / "app" / "ml_models" / "risk_tier_rf.pkl"
            CONFIG["reduced_model_path"] = (
                BACKEND_DIR / "app" / "ml_models" / "risk_tier_rf_reduced_4items.pkl"
            )
    results_dir = Path(CONFIG["results_dir"])
    results_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = Path(CONFIG["cohort_path"])
    if not cohort_path.is_file():
        raise FileNotFoundError(
            f"saved cohort is required; run the existing cohort generator first: {cohort_path}"
        )
    cohort = _read_cohort(cohort_path)
    logged_records = _build_logged_records()

    replay_summary, mismatch_rows, completeness_summary, part_a = _analyze_replay_and_traces(
        cohort,
        logged_records,
    )
    unlock_rows = part_a["unlock_rows"]
    unlock_summary = _unlock_summaries(unlock_rows)
    emi_boundary_summary = _emi_boundary_summary(unlock_rows)
    suspect_case = _suspect_boundary_case()
    unlock_failures = [dict(row) for row in unlock_rows if not row["valid"]]
    for row in unlock_failures:
        if row["dataset"] == "logged_database":
            row["emi_ratio_after"] = ""
    gap_rows = part_a["gap_rows"]
    shap_results = _run_shap_analysis()
    plot_path = _write_faithfulness_plot(results_dir, shap_results["plot_data"])

    replay_path = results_dir / "faithfulness_replay_summary.csv"
    mismatch_path = results_dir / "faithfulness_replay_mismatches.csv"
    unlock_summary_path = results_dir / "faithfulness_unlock_summary.csv"
    emi_boundary_path = results_dir / "faithfulness_emi_boundary_summary.csv"
    suspect_case_path = results_dir / "faithfulness_suspect_boundary_case.csv"
    unlock_failures_path = results_dir / "faithfulness_unlock_failures.csv"
    completeness_path = results_dir / "faithfulness_trace_completeness.csv"
    gaps_path = results_dir / "faithfulness_trace_gaps.csv"
    additivity_path = results_dir / "shap_additivity.csv"
    deletion_path = results_dir / "shap_deletion_summary.csv"
    comparison_path = results_dir / "shap_deletion_comparisons.csv"
    importance_path = results_dir / "shap_feature_importance.csv"
    stability_path = results_dir / "shap_rank_stability.csv"
    report_path = results_dir / "results.md"

    csv_tables = (
        (replay_path, replay_summary, ["dataset", "traces", "matched", "mismatched", "match_rate", "ci95_low", "ci95_high"]),
        (mismatch_path, mismatch_rows, ["dataset", "record_id", "mismatch_fields"]),
        (unlock_summary_path, unlock_summary, ["dataset", "constraint", "conditions", "valid", "failed", "valid_share", "ci95_low", "ci95_high"]),
        (emi_boundary_path, emi_boundary_summary, ["dataset", "promised_tier", "conditions", "exclusive_upper_threshold", "at_exclusive_threshold", "above_exclusive_threshold", "at_threshold_share", "at_threshold_ci95_low", "at_threshold_ci95_high", "failed_at_threshold", "failed_at_threshold_share", "failed_threshold_ci95_low", "failed_threshold_ci95_high", "at_or_above_exclusive_threshold", "at_or_above_threshold_share", "at_or_above_ci95_low", "at_or_above_ci95_high", "failed_at_or_above_threshold", "failed_at_or_above_share", "failed_at_or_above_ci95_low", "failed_at_or_above_ci95_high", "failed_total"]),
        (suspect_case_path, [suspect_case], ["monthly_income_rupees", "monthly_emi_rupees", "requested_reduction_rupees", "emi_ratio_before", "displayed_instruction", "promised_tier", "capacity_ceiling_before", "emi_ratio_after", "capacity_ceiling_after", "unlock_valid", "upper_band_boundary"]),
        (unlock_failures_path, unlock_failures, ["dataset", "record_id", "constraint", "promised_tier", "ceiling_before", "ceiling_after", "emi_ratio_after", "valid", "reason", "instruction"]),
        (completeness_path, completeness_summary, ["dataset", "traces", "gaps", "complete", "gap_share", "ci95_low", "ci95_high"]),
        (gaps_path, gap_rows, ["dataset", "record_id", "missing_fields"]),
        (additivity_path, shap_results["additivity_rows"], ["model", "n_test", "tolerance", "mean_absolute_error", "mean_error_ci95_low", "mean_error_ci95_high", "maximum_absolute_error", "within_tolerance", "within_tolerance_share", "share_ci95_low", "share_ci95_high"]),
        (deletion_path, shap_results["deletion_rows"], ["model", "method", "features_evaluated_per_profile", "mean_predicted_class_probability_drop", "ci95_low", "ci95_high"]),
        (comparison_path, shap_results["comparison_rows"], ["model", "comparison", "mean_paired_drop_difference", "ci95_low", "ci95_high"]),
        (importance_path, shap_results["importance_rows"], ["model", "feature", "feature_label", "mean_absolute_shap", "ci95_low", "ci95_high"]),
        (stability_path, shap_results["stability_rows"], ["model", "n_test", "rank_spearman_mean", "ci95_low", "ci95_high", "bootstrap_replicates"]),
    )
    for output_path, rows, columns in csv_tables:
        _write_csv(output_path, rows, columns)

    versions = {
        "Python": platform.python_version(),
        "NumPy": np.__version__,
        "SciPy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "SHAP": shap.__version__,
        "Matplotlib": matplotlib.__version__,
    }
    _write_results_report(
        report_path,
        replay_summary,
        mismatch_rows,
        unlock_summary,
        emi_boundary_summary,
        suspect_case,
        unlock_failures,
        completeness_summary,
        gap_rows,
        shap_results,
        versions,
    )
    study_paths = _write_user_study_kit(part_a["cohort_scenarios"])
    summary_path = results_dir / "faithfulness_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "config": {
                    key: str(value) if isinstance(value, Path) else value
                    for key, value in CONFIG.items()
                },
                "versions": versions,
                "cohort_profiles": len(cohort),
                "logged_risk_profile_events": len(logged_records),
                "replay_summary": replay_summary,
                "replay_mismatches": mismatch_rows,
                "unlock_summary": unlock_summary,
                "emi_boundary_summary": emi_boundary_summary,
                "suspect_emi_boundary_case": suspect_case,
                "unlock_failures": unlock_failures,
                "trace_completeness": completeness_summary,
                "trace_gaps": gap_rows,
                "shap_additivity": shap_results["additivity_rows"],
                "shap_deletion": shap_results["deletion_rows"],
                "shap_deletion_comparisons": shap_results["comparison_rows"],
                "shap_feature_importance": shap_results["importance_rows"],
                "shap_rank_stability": shap_results["stability_rows"],
                "model_split_sizes": shap_results["split_sizes"],
                "model_load_warnings": shap_results["warning_messages"],
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs = {
        "report": report_path,
        "replay_summary": replay_path,
        "replay_mismatches": mismatch_path,
        "unlock_summary": unlock_summary_path,
        "emi_boundary_summary": emi_boundary_path,
        "suspect_boundary_case": suspect_case_path,
        "unlock_failures": unlock_failures_path,
        "trace_completeness": completeness_path,
        "trace_gaps": gaps_path,
        "shap_additivity": additivity_path,
        "shap_deletion": deletion_path,
        "shap_deletion_comparisons": comparison_path,
        "shap_feature_importance": importance_path,
        "shap_stability": stability_path,
        "shap_plot": plot_path,
        "summary": summary_path,
    }
    outputs.update({f"user_study_{index}": path for index, path in enumerate(study_paths, start=1)})
    for label, path in outputs.items():
        print(f"{label}: {path}")
    print(f"logged_risk_profile_events: {len(logged_records)}")
    print(f"cohort_profiles: {len(cohort)}")
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-version",
        choices=("old", "v2"),
        help="write an isolated old or v2 model comparison run under results_v2/",
    )
    parser.add_argument(
        "--unlock-fix",
        action="store_true",
        help="run the v2 unlock comparison without overwriting existing experiment outputs",
    )
    arguments = parser.parse_args()
    if arguments.unlock_fix:
        from research_artifacts.experiments.unlock_fix_analysis import run_analysis as run_unlock_fix

        run_unlock_fix()
    else:
        run_analysis(arguments.model_version)
