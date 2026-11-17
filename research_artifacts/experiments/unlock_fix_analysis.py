"""Compare legacy single unlocks with the joint unlock plan on saved inputs."""

from __future__ import annotations

import csv
import json
import math
import platform
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
for import_path in (ROOT, BACKEND_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.services.risk_profile import (  # noqa: E402
    CapacityInputs,
    IncomeStabilityValue,
    StatedTierResult,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import (  # noqa: E402
    CAPACITY_RULE_TABLE_V1,
    QUESTIONNAIRE_V1,
    QUESTIONNAIRE_V2,
)
from research_artifacts.experiments import faithfulness  # noqa: E402
from research_artifacts.experiments.cohort import COHORT_CONFIG  # noqa: E402
from research_artifacts.experiments.common import capacity_inputs_from_profile  # noqa: E402


# Reproducibility settings are kept together; the saved cohort is not regenerated.
CONFIG: dict[str, Any] = {
    "seed": 42,
    "cohort_path": ROOT / "research_artifacts" / "experiments" / "results" / "cohort.csv",
    "database_path": ROOT / "backend" / "dev.db",
    "results_dir": ROOT / "research_artifacts" / "experiments" / "results_v2",
}

QUESTIONNAIRES = {
    QUESTIONNAIRE_V1.version: QUESTIONNAIRE_V1,
    QUESTIONNAIRE_V2.version: QUESTIONNAIRE_V2,
}


def _format_rupees(paise: int) -> str:
    value = str(abs(paise // 100))
    if len(value) > 3:
        groups = [value[-3:]]
        value = value[:-3]
        while value:
            groups.insert(0, value[-2:])
            value = value[:-2]
        value = ",".join(groups)
    return f"Rs {'-' if paise < 0 else ''}{value}"


def _legacy_conditions(inputs: CapacityInputs, target: int) -> list[dict[str, Any]]:
    capacity = compute_capacity_ceiling(inputs)
    result: list[dict[str, Any]] = []
    for component in capacity.components:
        if not component.applicable or component.ceiling != capacity.ceiling:
            continue
        if component.name == "income_stability":
            result.append(
                {
                    "constraint": "income_stability",
                    "message": (
                        "This cap is tied to income stability: it lifts once your income is regular "
                        "(steady, predictable pay each month) rather than irregular. There is no "
                        "partial credit for this constraint in the current rule table."
                    ),
                    "current_value": "irregular",
                    "target_value": "regular",
                }
            )
            continue
        if component.name == "buffer_months":
            band = next(band for band in CAPACITY_RULE_TABLE_V1.buffer_months_bands if band.ceiling == target)
            months = Decimal(str(band.min_value))
            required_paise = int(
                (months * Decimal(inputs.essential_monthly_expense_paise)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            shortfall = max(0, required_paise - inputs.cash_balance_paise)
            result.append(
                {
                    "constraint": component.name,
                    "message": (
                        f"Reach {months} months of emergency buffer - you need "
                        f"{_format_rupees(shortfall)} more in cash savings."
                    ),
                    "current_value": f"{inputs.buffer_coverage_months} months",
                    "target_value": f"{months} months",
                }
            )
        elif component.name == "emi_to_income_ratio":
            band = next(band for band in CAPACITY_RULE_TABLE_V1.emi_to_income_bands if band.ceiling == target)
            boundary = Decimal(str(band.max_value))
            required_emi = int(
                (boundary * Decimal(inputs.monthly_income_paise)).to_integral_value(rounding=ROUND_FLOOR)
            )
            reduction = max(0, inputs.total_monthly_emi_paise - required_emi)
            result.append(
                {
                    "constraint": component.name,
                    "message": (
                        f"Bring your EMI-to-income ratio below {boundary * 100:.0f}% - "
                        f"reduce your monthly EMI outflow by {_format_rupees(reduction)}."
                    ),
                    "current_value": f"{inputs.emi_to_income_ratio * 100:.1f}%",
                    "target_value": f"below {boundary * 100:.0f}%",
                }
            )
        elif component.name == "insurance_adequacy":
            band = next(
                band for band in CAPACITY_RULE_TABLE_V1.insurance_coverage_bands if band.ceiling == target
            )
            ratio = Decimal(str(band.min_value))
            base = Decimal(
                inputs.monthly_income_paise
                * 12
                * CAPACITY_RULE_TABLE_V1.required_life_cover_income_multiple
            )
            required_cover = int((ratio * base).to_integral_value(rounding=ROUND_CEILING))
            shortfall = max(0, required_cover - inputs.total_life_cover_paise)
            result.append(
                {
                    "constraint": component.name,
                    "message": (
                        f"Increase life insurance cover by {_format_rupees(shortfall)} to reach at least "
                        f"{_format_rupees(required_cover)} total sum assured for your "
                        f"{inputs.dependents_count} dependent(s)."
                    ),
                    "current_value": _format_rupees(inputs.total_life_cover_paise),
                    "target_value": f"at least {_format_rupees(required_cover)}",
                }
            )
    return result


def _stated_result(suggested: dict[str, Any]) -> StatedTierResult:
    version = str(suggested.get("questionnaire_version") or QUESTIONNAIRE_V2.version)
    questionnaire = QUESTIONNAIRES[version]
    answers = suggested.get("answers") or {}
    if all(question.id in answers for question in questionnaire.questions):
        return compute_stated_tier(
            {question.id: str(answers[question.id]) for question in questionnaire.questions},
            questionnaire,
        )
    return StatedTierResult(
        questionnaire_version=version,
        score=int(suggested.get("stated_score", 0)),
        tier=int(suggested["stated_tier"]),
        estimation_method=str(suggested.get("estimation_method", "deterministic")),
    )


def _apply_conditions(
    inputs: CapacityInputs,
    conditions: list[dict[str, Any]],
) -> tuple[CapacityInputs | None, str | None]:
    updated = inputs
    for condition in conditions:
        if condition.get("constraint") == "income_stability":
            return None, "income stability is non-actionable"
        updated, error = faithfulness.apply_unlock_condition(updated, condition)
        if error or updated is None:
            return None, error or "unable to apply unlock condition"
    return updated, None


def _failure_reason(
    *,
    constraint: str | None,
    updated: CapacityInputs | None,
    goal: int,
    achievable_tier: int,
    binding_count: int,
    blocking_constraints: tuple[str, ...],
    current_inputs: CapacityInputs | None,
    error: str | None,
) -> str:
    if error or updated is None or constraint == "income_stability":
        return "non_actionable"
    if goal > achievable_tier and blocking_constraints:
        return "non_actionable"
    if constraint == "emi_to_income_ratio":
        target_band = next(
            band for band in CAPACITY_RULE_TABLE_V1.emi_to_income_bands if band.ceiling == goal
        )
        if target_band.max_value is not None and updated.emi_to_income_ratio >= Decimal(str(target_band.max_value)):
            return "boundary"
    after = compute_capacity_ceiling(updated)
    if after.ceiling >= goal:
        return ""
    remaining = [
        component
        for component in after.components
        if component.applicable and component.ceiling < goal and component.name != constraint
    ]
    if binding_count > 1 and current_inputs is not None and remaining:
        return "tie"
    if remaining:
        return "next_constraint"
    return "next_constraint"


def _failure_row(
    *,
    dataset: str,
    record_id: str,
    logic: str,
    check: str,
    constraint: str | None,
    goal: int,
    achievable_tier: int,
    ceiling_before: int | None,
    updated: CapacityInputs | None,
    binding_count: int,
    blocking_constraints: tuple[str, ...],
    inputs: CapacityInputs | None,
    error: str | None,
    instruction: str,
) -> dict[str, Any]:
    ceiling_after = (
        compute_capacity_ceiling(updated).ceiling if updated is not None else ""
    )
    reason = _failure_reason(
        constraint=constraint,
        updated=updated,
        goal=goal,
        achievable_tier=achievable_tier,
        binding_count=binding_count,
        blocking_constraints=blocking_constraints if goal > achievable_tier else (),
        current_inputs=inputs,
        error=error,
    )
    return {
        "dataset": dataset,
        "record_id": record_id,
        "logic": logic,
        "check": check,
        "constraint": constraint or "",
        "goal_tier": goal,
        "achievable_tier": achievable_tier,
        "ceiling_before": ceiling_before if ceiling_before is not None else "",
        "ceiling_after": ceiling_after,
        "reason": reason or "next_constraint",
        "instruction": instruction,
    }


def _records() -> list[dict[str, Any]]:
    if int(CONFIG["seed"]) != int(COHORT_CONFIG["seed"]):
        raise ValueError("configured seed differs from the saved cohort seed")
    if Path(faithfulness.CONFIG["database_path"]) != Path(CONFIG["database_path"]):
        raise ValueError("configured database differs from the faithfulness input database")
    cohort = faithfulness._read_cohort(Path(CONFIG["cohort_path"]))
    records: list[dict[str, Any]] = []
    for index, profile in enumerate(cohort, start=1):
        suggested, context = faithfulness._profile_decision(profile)
        records.append(
            {
                "dataset": "synthetic_cohort",
                "record_id": str(profile.get("profile_id") or f"cohort-{index:05d}"),
                "suggested": suggested,
                "context": context,
                "inputs": capacity_inputs_from_profile(profile),
            }
        )
    for record in faithfulness._build_logged_records():
        try:
            inputs = faithfulness._capacity_for_logged_context(record["market_context"])
        except (ValueError, KeyError, TypeError):
            inputs = None
        records.append(
            {
                "dataset": "logged_database",
                "record_id": record["record_id"],
                "suggested": record["suggested_value"],
                "context": record["market_context"],
                "inputs": inputs,
            }
        )
    return records


def _analyze() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    action_rows: list[dict[str, Any]] = []
    joint_rows: list[dict[str, Any]] = []
    revisions: dict[str, list[bool]] = defaultdict(list)
    capped_counts: Counter[str] = Counter()

    for record in _records():
        suggested = record["suggested"]
        inputs = record["inputs"]
        dataset = record["dataset"]
        if not suggested.get("capped"):
            revisions[dataset].append(False)
            continue
        record_id = record["record_id"]
        capped_counts[dataset] += 1
        stated_tier = int(suggested["stated_tier"])

        if inputs is None:
            for logic in ("OLD", "NEW"):
                failure = _failure_row(
                    dataset=dataset,
                    record_id=record_id,
                    logic=logic,
                    check="single_action",
                    constraint=None,
                    goal=stated_tier,
                    achievable_tier=stated_tier,
                    ceiling_before=suggested.get("capacity_ceiling"),
                    updated=None,
                    binding_count=0,
                    blocking_constraints=(),
                    inputs=None,
                    error="missing capacity inputs",
                    instruction="",
                )
                action_rows.append({**failure, "binding_group": "uniquely_binding_conditions", "valid": False})
                joint_rows.append({**failure, "check": "joint_plan", "binding_group": "all", "valid": False})
            revisions[dataset].append(False)
            continue

        capacity = compute_capacity_ceiling(inputs)
        stated = _stated_result(suggested)
        new_result = compute_final_tier(stated, capacity, inputs)
        old_conditions = (
            suggested.get("unlock_conditions")
            if dataset == "logged_database"
            else None
        )
        if not old_conditions:
            old_conditions = _legacy_conditions(inputs, stated_tier)
        old_conditions = [dict(condition) for condition in old_conditions]
        new_conditions = [
            condition.__dict__ for condition in new_result.unlock_conditions
        ]
        new_plan = [action.__dict__ for action in new_result.joint_unlock_plan]
        binding_count = len(new_result.binding_constraints)
        binding_group = (
            "tied_conditions" if binding_count > 1 else "uniquely_binding_conditions"
        )
        revisions[dataset].append(new_result.achievable_tier < stated_tier)

        for logic, conditions, goal, blockers in (
            ("OLD", old_conditions, stated_tier, new_result.blocking_constraints),
            (
                "NEW",
                new_conditions,
                int(new_result.achievable_tier),
                new_result.blocking_constraints,
            ),
        ):
            for condition in conditions:
                constraint = str(condition.get("constraint", ""))
                updated, error = _apply_conditions(inputs, [condition])
                ceiling_after = (
                    compute_capacity_ceiling(updated).ceiling if updated is not None else ""
                )
                valid = updated is not None and ceiling_after >= goal
                failure = _failure_row(
                    dataset=dataset,
                    record_id=record_id,
                    logic=logic,
                    check="single_action",
                    constraint=constraint,
                    goal=goal,
                    achievable_tier=int(new_result.achievable_tier),
                    ceiling_before=capacity.ceiling,
                    updated=updated,
                    binding_count=binding_count,
                    blocking_constraints=blockers,
                    inputs=inputs,
                    error=error,
                    instruction=str(condition.get("message", "")),
                )
                action_rows.append(
                    {
                        **failure,
                        "binding_group": binding_group,
                        "valid": bool(valid),
                        "failure_reason": "" if valid else failure["reason"],
                    }
                )

        old_updated, old_error = _apply_conditions(inputs, old_conditions)
        old_valid = (
            old_updated is not None
            and compute_capacity_ceiling(old_updated).ceiling >= stated_tier
        )
        old_joint = _failure_row(
            dataset=dataset,
            record_id=record_id,
            logic="OLD",
            check="joint_actions",
            constraint=None,
            goal=stated_tier,
            achievable_tier=int(new_result.achievable_tier),
            ceiling_before=capacity.ceiling,
            updated=old_updated,
            binding_count=binding_count,
            blocking_constraints=new_result.blocking_constraints,
            inputs=inputs,
            error=old_error,
            instruction="; ".join(str(action.get("message", "")) for action in old_conditions),
        )
        joint_rows.append({**old_joint, "binding_group": "all", "valid": bool(old_valid)})

        new_updated, new_error = _apply_conditions(inputs, new_plan)
        new_goal = int(new_result.achievable_tier)
        new_valid = (
            new_updated is not None
            and compute_capacity_ceiling(new_updated).ceiling >= new_goal
        )
        new_joint = _failure_row(
            dataset=dataset,
            record_id=record_id,
            logic="NEW",
            check="joint_plan",
            constraint=None,
            goal=new_goal,
            achievable_tier=new_goal,
            ceiling_before=capacity.ceiling,
            updated=new_updated,
            binding_count=binding_count,
            blocking_constraints=new_result.blocking_constraints,
            inputs=inputs,
            error=new_error,
            instruction="; ".join(str(action.get("message", "")) for action in new_plan),
        )
        joint_rows.append({**new_joint, "binding_group": "all", "valid": bool(new_valid)})

    return action_rows, joint_rows, [
        {
            "dataset": dataset,
            "profiles": len(outcomes),
            "capped_profiles": capped_counts[dataset],
            "lower_achievable_tier": sum(outcomes),
            "share_of_capped_profiles": (
                sum(outcomes) / capped_counts[dataset] if capped_counts[dataset] else math.nan
            ),
            "share_of_all_profiles": sum(outcomes) / len(outcomes) if outcomes else math.nan,
        }
        for dataset, outcomes in sorted(revisions.items())
    ]


def _summary_rows(
    action_rows: list[dict[str, Any]], joint_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    summaries = []
    for dataset in sorted({row["dataset"] for row in action_rows}):
        for logic in ("OLD", "NEW"):
            for group in ("tied_conditions", "uniquely_binding_conditions"):
                rows = [
                    row
                    for row in action_rows
                    if row["dataset"] == dataset
                    and row["logic"] == logic
                    and row["binding_group"] == group
                ]
                if rows:
                    valid_count = sum(bool(row["valid"]) for row in rows)
                    summaries.append(
                        {
                            "dataset": dataset,
                            "logic": logic,
                            "check": "single_action",
                            "binding_group": group,
                            "goal": "stated_tier" if logic == "OLD" else "achievable_tier",
                            "conditions": len(rows),
                            "valid": valid_count,
                            "failed": len(rows) - valid_count,
                            "valid_share": valid_count / len(rows),
                        }
                    )
            for check in ("joint_actions", "joint_plan"):
                rows = [
                    row
                    for row in joint_rows
                    if row["dataset"] == dataset and row["logic"] == logic and row["check"] == check
                ]
                if rows:
                    valid_count = sum(bool(row["valid"]) for row in rows)
                    summaries.append(
                        {
                            "dataset": dataset,
                            "logic": logic,
                            "check": check,
                            "binding_group": "all",
                            "goal": "stated_tier" if logic == "OLD" else "achievable_tier",
                            "conditions": len(rows),
                            "valid": valid_count,
                            "failed": len(rows) - valid_count,
                            "valid_share": valid_count / len(rows),
                        }
                    )
    return summaries


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(str(row.get(key, "")) for key, _ in columns) + " |"
        for row in rows
    )
    return lines


def _write_report(
    path: Path,
    summary: list[dict[str, Any]],
    revisions: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    versions: dict[str, str],
    failure_details_path: Path,
) -> None:
    reason_counts = Counter(
        (row["dataset"], row["logic"], row["reason"])
        for row in failures
    )
    reason_rows = [
        {"dataset": dataset, "logic": logic, "reason": reason, "failures": count}
        for (dataset, logic, reason), count in sorted(reason_counts.items())
    ]
    lines = [
        "# Unlock fix results",
        "",
        f"Seed: {CONFIG['seed']}",
        f"Synthetic cohort: {CONFIG['cohort_path']}",
        f"Logged database: {CONFIG['database_path']}",
        "",
        "## Library versions",
        "",
        *_markdown_table(
            [{"library": key, "version": value} for key, value in versions.items()],
            [("library", "Library"), ("version", "Version")],
        ),
        "",
        "## OLD versus NEW single-action validity",
        "",
        *_markdown_table(
            [row for row in summary if row["check"] == "single_action"],
            [
                ("dataset", "Dataset"),
                ("logic", "Logic"),
                ("check", "Check"),
                ("binding_group", "Binding group"),
                ("goal", "Goal"),
                ("conditions", "Conditions"),
                ("valid", "Valid"),
                ("failed", "Failed"),
                ("valid_share", "Valid share"),
            ],
        ),
        "",
        "## OLD action bundle versus NEW joint-plan validity",
        "",
        *_markdown_table(
            [row for row in summary if row["check"] != "single_action"],
            [
                ("dataset", "Dataset"),
                ("logic", "Logic"),
                ("check", "Check"),
                ("goal", "Goal"),
                ("conditions", "Capped profiles"),
                ("valid", "Valid"),
                ("failed", "Failed"),
                ("valid_share", "Valid share"),
            ],
        ),
        "",
        "## Profiles with a lower achievable tier",
        "",
        *_markdown_table(
            revisions,
            [
                ("dataset", "Dataset"),
                ("profiles", "Profiles"),
                ("capped_profiles", "Capped profiles"),
                ("lower_achievable_tier", "Lower achievable tier"),
                ("share_of_capped_profiles", "Share of capped profiles"),
                ("share_of_all_profiles", "Share of all profiles"),
            ],
        ),
        "",
        "## Classified failures",
        "",
        f"Per-action and per-profile failure rows: {len(failures)}.",
        f"Details: [{failure_details_path.name}]({failure_details_path.name})",
        "",
        *_markdown_table(
            reason_rows,
            [
                ("dataset", "Dataset"),
                ("logic", "Logic"),
                ("reason", "Reason"),
                ("failures", "Failures"),
            ],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_analysis() -> dict[str, Path]:
    results_dir = Path(CONFIG["results_dir"])
    results_dir.mkdir(parents=True, exist_ok=True)
    action_rows, joint_rows, revisions = _analyze()
    summary = _summary_rows(action_rows, joint_rows)
    failures = [
        {
            **row,
            "instruction": (
                re.sub(r"\bRs\s+[\d,]+", "Rs [redacted]", str(row.get("instruction", "")))
                if row["dataset"] == "logged_database"
                else row.get("instruction", "")
            ),
        }
        for row in [*action_rows, *joint_rows]
        if not row["valid"]
    ]
    failure_path = results_dir / "unlock_remaining_failures.csv"
    summary_path = results_dir / "faithfulness_unlock_summary.csv"
    revision_path = results_dir / "unlock_tier_revisions.csv"
    _write_csv(
        failure_path,
        failures,
        [
            "dataset",
            "record_id",
            "logic",
            "check",
            "binding_group",
            "constraint",
            "goal_tier",
            "achievable_tier",
            "ceiling_before",
            "ceiling_after",
            "reason",
            "failure_reason",
            "instruction",
        ],
    )
    _write_csv(
        summary_path,
        summary,
        [
            "dataset",
            "logic",
            "check",
            "binding_group",
            "goal",
            "conditions",
            "valid",
            "failed",
            "valid_share",
        ],
    )
    _write_csv(
        revision_path,
        revisions,
        [
            "dataset",
            "profiles",
            "capped_profiles",
            "lower_achievable_tier",
            "share_of_capped_profiles",
            "share_of_all_profiles",
        ],
    )
    versions = {
        "Python": platform.python_version(),
        "NumPy": faithfulness.np.__version__,
        "SciPy": faithfulness.scipy.__version__,
        "scikit-learn": faithfulness.sklearn.__version__,
        "SHAP": faithfulness.shap.__version__,
    }
    report_path = results_dir / "unlock_fix_results.md"
    _write_report(report_path, summary, revisions, failures, versions, failure_path)
    metadata_path = results_dir / "unlock_fix_run.json"
    metadata_path.write_text(
        json.dumps(
            {
                "config": {key: str(value) if isinstance(value, Path) else value for key, value in CONFIG.items()},
                "versions": versions,
                "cohort_profiles": len(faithfulness._read_cohort(Path(CONFIG["cohort_path"]))),
                "logged_risk_profile_rows": len(faithfulness._build_logged_records()),
                "summary": summary,
                "tier_revisions": revisions,
                "classified_failure_count": len(failures),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"versions": versions, "outputs": {key: str(value) for key, value in {
        "report": report_path,
        "summary": summary_path,
        "tier_revisions": revision_path,
        "failures": failure_path,
        "metadata": metadata_path,
    }.items()}}, indent=2))
    return {
        "report": report_path,
        "summary": summary_path,
        "tier_revisions": revision_path,
        "failures": failure_path,
        "metadata": metadata_path,
    }


if __name__ == "__main__":
    run_analysis()
