"""Analyze when capacity components bind over willingness using saved data."""

from __future__ import annotations

import csv
import json
import platform
from collections import Counter
from dataclasses import replace
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.services.risk_profile import (
    CapacityResult,
    ComponentCeiling,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import (
    CAPACITY_RULE_TABLE_V1,
    QUESTIONNAIRE_V2,
    Band,
    CapacityRuleTable,
)

from research_artifacts.experiments.cohort import RESULTS_DIR, STRATUM_ORDER
from research_artifacts.experiments.common import capacity_inputs_from_profile


# All analysis options and non-cohort reference inputs are collected here.
# Demo values are transcribed from the named seed scripts; monetary seed
# fields in those scripts are integer paise and are retained as such here.
ANALYSIS_CONFIG: dict[str, Any] = {
    "cohort_csv": RESULTS_DIR / "cohort.csv",
    "results_dir": RESULTS_DIR,
    "threshold_perturbation_factors": (-0.10, 0.10),
    "heatmap_dpi": 160,
    "demo_profiles_paise": (
        {
            "profile_id": "seed_dummy_user",
            "source": "backend/scripts/seed_dummy_user.py",
            "monthly_income_paise": 120_000_00,
            "income_stability": "regular",
            "essential_expenses_paise": (25_000_00, 8_000_00, 3_000_00),
            "other_expenses_paise": (
                (6_000_00, "monthly"),
                (1_500_00, "monthly"),
                (60_000_00, "annual"),
            ),
            "cash_balance_paise": 300_000_00,
            "emi_amounts_paise": (22_000_00, 8_000_00),
            "dependents_count": 1,
            "life_cover_paise": 1_50_00_000_00,
            "answers": {
                "horizon": "7_15y",
                "drawdown_reaction": "hold",
                "experience": "moderate",
                "goal": "growth",
                "windfall_allocation": "split_debt_equity",
                "sure_gain_tradeoff": "chance_50pct_10000",
                "friend_description": "calculated_after_research",
            },
        },
        {
            "profile_id": "seed_showcase_user_initial",
            "source": "backend/scripts/seed_showcase_user.py (first risk-profile attempt)",
            "monthly_income_paise": 1_20_000_00,
            "income_stability": "regular",
            "essential_expenses_paise": (
                25_000_00,
                8_000_00,
                3_000_00,
                600_00,
                400_00,
            ),
            "other_expenses_paise": (
                (6_000_00, "monthly"),
                (650_00, "monthly"),
                (2_000_00, "monthly"),
                (120_00, "monthly"),
                (1_300_00, "annual"),
                (4_800_00, "annual"),
                (60_000_00, "annual"),
            ),
            "cash_balance_paise": 54_000_00,
            "emi_amounts_paise": (22_000_00, 4_500_00, 6_000_00, 2_500_00),
            "dependents_count": 1,
            "life_cover_paise": 1_00_00_000_00,
            "answers": {
                "horizon": "gt_15y",
                "drawdown_reaction": "buy_a_lot",
                "experience": "moderate",
                "goal": "growth",
                "windfall_allocation": "split_debt_equity",
                "sure_gain_tradeoff": "chance_50pct_10000",
                "friend_description": "calculated_after_research",
            },
        },
        {
            "profile_id": "seed_showcase_user_after_bonus",
            "source": "backend/scripts/seed_showcase_user.py (retake after bonus and EMI closure)",
            "monthly_income_paise": 1_20_000_00,
            "income_stability": "regular",
            "essential_expenses_paise": (
                25_000_00,
                8_000_00,
                3_000_00,
                600_00,
                400_00,
            ),
            "other_expenses_paise": (
                (6_000_00, "monthly"),
                (650_00, "monthly"),
                (2_000_00, "monthly"),
                (4_800_00, "annual"),
                (60_000_00, "annual"),
            ),
            "cash_balance_paise": 2_80_000_00,
            "emi_amounts_paise": (22_000_00, 4_500_00, 6_000_00),
            "dependents_count": 1,
            "life_cover_paise": 1_00_00_000_00,
            "answers": {
                "horizon": "gt_15y",
                "drawdown_reaction": "buy_a_lot",
                "experience": "moderate",
                "goal": "growth",
                "windfall_allocation": "split_debt_equity",
                "sure_gain_tradeoff": "chance_50pct_10000",
                "friend_description": "calculated_after_research",
            },
        },
        {
            "profile_id": "seed_feedback_demo_fl_growth",
            "source": "backend/scripts/seed_feedback_demo.py (fl_growth)",
            "monthly_income_paise": 1_00_000_00,
            "income_stability": "regular",
            "essential_expenses_paise": (20_000_00, 5_000_00),
            "other_expenses_paise": (),
            "cash_balance_paise": 5_00_000_00,
            "emi_amounts_paise": (),
            "dependents_count": 0,
            "life_cover_paise": 0,
            "answers": {
                "horizon": "lt_1y",
                "drawdown_reaction": "sell_all",
                "experience": "none",
                "goal": "preserve",
                "windfall_allocation": "fd_or_savings",
                "sure_gain_tradeoff": "guaranteed_5000",
                "friend_description": "real_risk_avoider",
            },
        },
        {
            "profile_id": "seed_feedback_demo_fl_capped",
            "source": "backend/scripts/seed_feedback_demo.py (fl_capped)",
            "monthly_income_paise": 1_00_000_00,
            "income_stability": "regular",
            "essential_expenses_paise": (20_000_00,),
            "other_expenses_paise": (),
            "cash_balance_paise": 30_000_00,
            "emi_amounts_paise": (),
            "dependents_count": 0,
            "life_cover_paise": 0,
            "answers": {
                "horizon": "gt_15y",
                "drawdown_reaction": "buy_a_lot",
                "experience": "extensive",
                "goal": "maximize",
                "windfall_allocation": "equity_plus_borrow",
                "sure_gain_tradeoff": "chance_10pct_50000",
                "friend_description": "real_gambler",
            },
        },
    ),
}

COMPONENTS = (
    ("buffer_months", "Emergency buffer"),
    ("emi_to_income_ratio", "EMI burden"),
    ("income_stability", "Income stability"),
    ("insurance_adequacy", "Insurance"),
)
THRESHOLD_BAND_FIELDS = (
    ("buffer_months_bands", "emergency_buffer_months"),
    ("emi_to_income_bands", "emi_to_income_ratio"),
    ("insurance_coverage_bands", "insurance_coverage_ratio"),
)


def load_saved_cohort(path: Path | None = None) -> list[dict[str, Any]]:
    """Load the previously generated cohort without regenerating it."""
    cohort_path = path or Path(ANALYSIS_CONFIG["cohort_csv"])
    if not cohort_path.is_file():
        raise FileNotFoundError(
            f"Saved cohort not found at {cohort_path}; run the original cohort "
            "generation command once before this analysis. This analysis does not regenerate it."
        )
    with cohort_path.open(encoding="utf-8", newline="") as csv_file:
        profiles = list(csv.DictReader(csv_file))
    if not profiles:
        raise ValueError(f"saved cohort is empty: {cohort_path}")
    expected_questions = {question.id for question in QUESTIONNAIRE_V2.questions}
    for profile in profiles:
        missing = expected_questions - profile.keys()
        if missing:
            raise ValueError(f"{profile.get('profile_id', '<unknown>')} missing answers: {sorted(missing)}")
        profile.update(
            {
                field: int(profile[field])
                for field in (
                    "monthly_income",
                    "essential_monthly_expense",
                    "other_monthly_expense",
                    "liquid_cash",
                    "total_monthly_emi",
                    "dependents_count",
                    "total_life_cover",
                )
            }
        )
    return profiles


def build_demo_profiles() -> list[dict[str, Any]]:
    """Adapt each eligible seeded-user fixture to the cohort profile shape."""
    profiles: list[dict[str, Any]] = []
    for fixture in ANALYSIS_CONFIG["demo_profiles_paise"]:
        monthly_income = int(fixture["monthly_income_paise"]) // 100
        essential_expense = sum(int(value) for value in fixture["essential_expenses_paise"]) // 100
        other_expense = int(
            sum(
                (
                    Decimal(int(amount)) / Decimal(100 if frequency == "monthly" else 1200)
                    for amount, frequency in fixture["other_expenses_paise"]
                ),
                start=Decimal(0),
            ).to_integral_value(rounding=ROUND_HALF_UP)
        )
        if monthly_income <= 0 or essential_expense <= 0:
            raise ValueError(f"invalid income/essential expense in demo fixture {fixture['profile_id']}")
        profiles.append(
            {
                "profile_id": fixture["profile_id"],
                "stratum": "demo_data",
                "demo_source": fixture["source"],
                "monthly_income": monthly_income,
                "income_stability": fixture["income_stability"],
                "essential_monthly_expense": essential_expense,
                "other_monthly_expense": other_expense,
                "liquid_cash": int(fixture["cash_balance_paise"]) // 100,
                "total_monthly_emi": sum(int(value) for value in fixture["emi_amounts_paise"]) // 100,
                "dependents_count": int(fixture["dependents_count"]),
                "total_life_cover": int(fixture["life_cover_paise"]) // 100,
                **fixture["answers"],
            }
        )
    return profiles


def evaluate_profile(
    profile: dict[str, Any],
    rule_table: CapacityRuleTable = CAPACITY_RULE_TABLE_V1,
) -> dict[str, Any]:
    """Use production scoring and capacity functions for one profile."""
    answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
    stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
    inputs = capacity_inputs_from_profile(profile)
    capacity = compute_capacity_ceiling(inputs, rule_table)
    final = compute_final_tier(stated, capacity, inputs, rule_table)
    cap_applied = stated.tier > capacity.ceiling
    binding = binding_component_names(capacity)
    return {
        "stated_tier": stated.tier,
        "capacity_ceiling": capacity.ceiling,
        "final_tier": final.final_tier,
        "cap_applied": cap_applied,
        "tier_reduction": stated.tier - final.final_tier,
        "binding_components": binding,
        "capacity_result": capacity,
    }


def binding_component_names(capacity: CapacityResult) -> tuple[str, ...]:
    """Return all applicable components tied at the minimum ceiling."""
    applicable = [component for component in capacity.components if component.applicable]
    if not applicable:
        raise ValueError("capacity result has no applicable components")
    minimum = min(component.ceiling for component in applicable)
    return tuple(component.name for component in applicable if component.ceiling == minimum)


def _threshold_values(table: CapacityRuleTable) -> list[tuple[str, str, float]]:
    thresholds: list[tuple[str, str, float]] = []
    for field_name, label in THRESHOLD_BAND_FIELDS:
        values = sorted(
            {
                float(boundary)
                for band in getattr(table, field_name)
                for boundary in (band.min_value, band.max_value)
                if boundary is not None and float(boundary) > 0
            }
        )
        thresholds.extend((field_name, label, value) for value in values)
    thresholds.append(
        (
            "required_life_cover_income_multiple",
            "required_life_cover_income_multiple",
            float(table.required_life_cover_income_multiple),
        )
    )
    thresholds.extend(
        (
            field_name,
            field_name,
            float(getattr(table, field_name)),
        )
        for field_name in ("irregular_income_ceiling", "regular_income_ceiling")
    )
    return thresholds


def perturb_capacity_threshold(
    table: CapacityRuleTable,
    field_name: str,
    threshold: float,
    factor: float,
) -> CapacityRuleTable:
    """Return a copied table with one continuous threshold shifted in place."""
    if factor not in ANALYSIS_CONFIG["threshold_perturbation_factors"]:
        raise ValueError(f"unsupported threshold perturbation factor: {factor}")
    shifted = float(threshold) * (1 + float(factor))
    if field_name == "required_life_cover_income_multiple":
        if shifted <= 0:
            raise ValueError("required life-cover multiple must remain positive")
        return replace(
            table,
            version=f"{table.version}-life-cover-{factor:+.0%}",
            required_life_cover_income_multiple=int(round(shifted)),
        )
    if field_name in {"irregular_income_ceiling", "regular_income_ceiling"}:
        rounding = ROUND_FLOOR if factor < 0 else ROUND_CEILING
        adjusted_ceiling = int(Decimal(str(shifted)).to_integral_value(rounding=rounding))
        adjusted_ceiling = min(5, max(1, adjusted_ceiling))
        return replace(
            table,
            version=f"{table.version}-{field_name}-{factor:+.0%}",
            **{field_name: adjusted_ceiling},
        )
    if field_name not in {name for name, _ in THRESHOLD_BAND_FIELDS}:
        raise ValueError(f"unsupported threshold field: {field_name}")

    bands = getattr(table, field_name)
    updated: list[Band] = []
    for band in bands:
        minimum = shifted if float(band.min_value) == float(threshold) else band.min_value
        maximum = (
            shifted
            if band.max_value is not None and float(band.max_value) == float(threshold)
            else band.max_value
        )
        if maximum is not None and float(minimum) >= float(maximum):
            raise ValueError("threshold shift made a capacity band invalid")
        updated.append(replace(band, min_value=minimum, max_value=maximum))
    return replace(table, version=f"{table.version}-{field_name}-{threshold:g}-{factor:+.0%}", **{field_name: tuple(updated)})


def _dataset_records(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for profile in profiles:
        evaluated = evaluate_profile(profile)
        if "stated_tier" in profile and int(profile["stated_tier"]) != evaluated["stated_tier"]:
            raise ValueError(f"saved stated tier disagrees with production scoring for {profile['profile_id']}")
        if "capacity_ceiling" in profile and int(profile["capacity_ceiling"]) != evaluated["capacity_ceiling"]:
            raise ValueError(f"saved capacity ceiling disagrees with production rules for {profile['profile_id']}")
        result.append(
            {
                **profile,
                **{key: value for key, value in evaluated.items() if key != "capacity_result"},
            }
        )
    return result


def _dataset_name(record: dict[str, Any]) -> str:
    return "synthetic_cohort" if record["stratum"] != "demo_data" else str(record["profile_id"])


def _rate_row(name: str, stratum: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    capped = [record for record in records if record["cap_applied"]]
    return {
        "dataset": name,
        "stratum": stratum,
        "n_profiles": len(records),
        "capped_profiles": len(capped),
        "cap_rate": len(capped) / len(records) if records else 0.0,
    }


def _summarize_cap_rates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cohort_records = [record for record in records if record["stratum"] != "demo_data"]
    demo_records = [record for record in records if record["stratum"] == "demo_data"]
    rows = [_rate_row("synthetic_cohort", "all", cohort_records)]
    for stratum in STRATUM_ORDER:
        rows.append(
            _rate_row(
                "synthetic_cohort",
                stratum,
                [record for record in records if record["stratum"] == stratum],
            )
        )
    for demo in sorted({record["profile_id"] for record in demo_records}):
        rows.append(
            _rate_row(
                demo,
                "demo_data",
                [record for record in demo_records if record["profile_id"] == demo],
            )
        )
    return rows


def _component_rows(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    tie_rows: list[dict[str, Any]] = []
    cohort_records = [record for record in records if record["stratum"] != "demo_data"]
    demo_records = [record for record in records if record["stratum"] == "demo_data"]
    groups = [("synthetic_cohort", "all", cohort_records)] + [
        ("synthetic_cohort", stratum, [record for record in cohort_records if record["stratum"] == stratum])
        for stratum in STRATUM_ORDER
    ]
    groups.extend(
        (record["profile_id"], record["profile_id"], [record])
        for record in demo_records
    )

    for dataset, group_name, group_records in groups:
        capped_records = [record for record in group_records if record["cap_applied"]]
        tie_counts: Counter[str] = Counter()
        for record in capped_records:
            tie_counts[" + ".join(sorted(record["binding_components"]))] += 1
        for component_name, component_label in COMPONENTS:
            unique_count = sum(
                len(record["binding_components"]) == 1
                and component_name in record["binding_components"]
                for record in capped_records
            )
            tied_count = sum(
                len(record["binding_components"]) > 1
                and component_name in record["binding_components"]
                for record in capped_records
            )
            rows.append(
                {
                    "dataset": dataset,
                    "stratum": group_name,
                    "component": component_name,
                    "component_label": component_label,
                    "profiles_in_group": len(group_records),
                    "capped_profiles": len(capped_records),
                    "unique_binding_count": unique_count,
                    "unique_binding_share_of_capped": unique_count / len(capped_records) if capped_records else 0.0,
                    "tied_binding_count": tied_count,
                    "tied_binding_share_of_capped": tied_count / len(capped_records) if capped_records else 0.0,
                    "any_binding_count": unique_count + tied_count,
                    "any_binding_share_of_capped": (unique_count + tied_count) / len(capped_records)
                    if capped_records
                    else 0.0,
                }
            )
        for combination, count in sorted(tie_counts.items()):
            tie_rows.append(
                {
                    "dataset": dataset,
                    "stratum": group_name,
                    "binding_component_set": combination,
                    "binding_type": "tied" if " + " in combination else "unique",
                    "profiles": count,
                    "share_of_capped": count / len(capped_records) if capped_records else 0.0,
                }
            )
    return rows, tie_rows


def _tier_matrices(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cohort_records = [record for record in records if record["stratum"] != "demo_data"]
    demo_records = [record for record in records if record["stratum"] == "demo_data"]
    groups: list[tuple[str, list[dict[str, Any]]]] = [("synthetic_cohort", cohort_records)]
    groups.extend(
        (stratum, [record for record in cohort_records if record["stratum"] == stratum])
        for stratum in STRATUM_ORDER
    )
    groups.extend(
        (record["profile_id"], [record])
        for record in demo_records
    )
    counts_rows: list[dict[str, Any]] = []
    percentages_rows: list[dict[str, Any]] = []
    for group_name, group_records in groups:
        matrix = np.zeros((5, 5), dtype=int)
        for record in group_records:
            matrix[int(record["stated_tier"]) - 1, int(record["final_tier"]) - 1] += 1
        row_totals = matrix.sum(axis=1)
        percentages = np.divide(
            matrix,
            row_totals[:, None],
            out=np.zeros((5, 5), dtype=float),
            where=row_totals[:, None] > 0,
        )
        dataset = "synthetic_cohort" if group_name in {"synthetic_cohort", *STRATUM_ORDER} else group_name
        stratum = "all" if group_name == "synthetic_cohort" else group_name
        for stated_index in range(5):
            common = {
                "dataset": dataset,
                "stratum": stratum,
                "stated_tier": stated_index + 1,
                "row_profiles": int(row_totals[stated_index]),
            }
            counts_rows.append(
                {**common, **{f"final_tier_{tier}": int(matrix[stated_index, tier - 1]) for tier in range(1, 6)}}
            )
            percentages_rows.append(
                {
                    **common,
                    **{
                        f"final_tier_{tier}_row_pct": float(percentages[stated_index, tier - 1])
                        for tier in range(1, 6)
                    },
                }
            )
    return counts_rows, percentages_rows


def _reduction_rows(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cohort_records = [record for record in records if record["stratum"] != "demo_data"]
    demo_records = [record for record in records if record["stratum"] == "demo_data"]
    groups: list[tuple[str, list[dict[str, Any]]]] = [("synthetic_cohort", cohort_records)]
    groups.extend(
        (stratum, [record for record in cohort_records if record["stratum"] == stratum])
        for stratum in STRATUM_ORDER
    )
    groups.extend(
        (record["profile_id"], [record])
        for record in demo_records
    )
    summary_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    for group_name, group_records in groups:
        capped = [record for record in group_records if record["cap_applied"]]
        reductions = Counter(int(record["tier_reduction"]) for record in capped)
        dataset = "synthetic_cohort" if group_name in {"synthetic_cohort", *STRATUM_ORDER} else group_name
        stratum = "all" if group_name == "synthetic_cohort" else group_name
        summary_rows.append(
            {
                "dataset": dataset,
                "stratum": stratum,
                "n_profiles": len(group_records),
                "capped_profiles": len(capped),
                "mean_reduction_when_capped": (
                    float(np.mean([record["tier_reduction"] for record in capped])) if capped else 0.0
                ),
            }
        )
        for size in range(1, 5):
            distribution_rows.append(
                {
                    "dataset": dataset,
                    "stratum": stratum,
                    "reduction_tiers": size,
                    "profiles": reductions[size],
                    "share_of_capped": reductions[size] / len(capped) if capped else 0.0,
                }
            )
    return summary_rows, distribution_rows


def _sensitivity_rows(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cohort_records = [record for record in records if record["stratum"] != "demo_data"]
    demo_records = [record for record in records if record["stratum"] == "demo_data"]
    dataset_groups: list[tuple[str, list[dict[str, Any]]]] = [("synthetic_cohort", cohort_records)]
    dataset_groups.extend(
        (record["profile_id"], [record])
        for record in demo_records
    )
    summary_rows: list[dict[str, Any]] = []
    tier_rows: list[dict[str, Any]] = []
    for dataset, profiles in dataset_groups:
        baseline = [_score_for_table(profile, CAPACITY_RULE_TABLE_V1) for profile in profiles]
        baseline_rate = sum(result["cap_applied"] for result in baseline) / len(baseline)
        baseline_tier_counts = Counter(result["final_tier"] for result in baseline)
        for field_name, label, threshold in _threshold_values(CAPACITY_RULE_TABLE_V1):
            for factor in ANALYSIS_CONFIG["threshold_perturbation_factors"]:
                perturbed = perturb_capacity_threshold(CAPACITY_RULE_TABLE_V1, field_name, threshold, factor)
                scenario = [_score_for_table(profile, perturbed) for profile in profiles]
                cap_rate = sum(result["cap_applied"] for result in scenario) / len(scenario)
                tier_counts = Counter(result["final_tier"] for result in scenario)
                name = f"{label}={threshold:g} ({factor:+.0%})"
                row = {
                    "dataset": dataset,
                    "threshold_name": label,
                    "base_threshold": threshold,
                    "perturbation": factor,
                    "scenario": name,
                    "n_profiles": len(profiles),
                    "baseline_cap_rate": baseline_rate,
                    "scenario_cap_rate": cap_rate,
                    "cap_rate_change_percentage_points": (cap_rate - baseline_rate) * 100,
                }
                for tier in range(1, 6):
                    baseline_share = baseline_tier_counts[tier] / len(profiles)
                    scenario_share = tier_counts[tier] / len(profiles)
                    row[f"final_tier_{tier}_baseline_share"] = baseline_share
                    row[f"final_tier_{tier}_scenario_share"] = scenario_share
                    row[f"final_tier_{tier}_change_percentage_points"] = (
                        scenario_share - baseline_share
                    ) * 100
                    tier_rows.append(
                        {
                            "dataset": dataset,
                            "scenario": name,
                            "threshold_name": label,
                            "base_threshold": threshold,
                            "perturbation": factor,
                            "final_tier": tier,
                            "baseline_profiles": baseline_tier_counts[tier],
                            "scenario_profiles": tier_counts[tier],
                            "baseline_share": baseline_share,
                            "scenario_share": scenario_share,
                            "share_change_percentage_points": (scenario_share - baseline_share) * 100,
                        }
                    )
                summary_rows.append(row)
    return summary_rows, tier_rows


def _score_for_table(profile: dict[str, Any], table: CapacityRuleTable) -> dict[str, Any]:
    answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
    stated = compute_stated_tier(answers, QUESTIONNAIRE_V2)
    capacity = compute_capacity_ceiling(capacity_inputs_from_profile(profile), table)
    return {
        "stated_tier": stated.tier,
        "capacity_ceiling": capacity.ceiling,
        "final_tier": min(stated.tier, capacity.ceiling),
        "cap_applied": stated.tier > capacity.ceiling,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty results table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot_tier_heatmap(records: list[dict[str, Any]], output_path: Path) -> None:
    matrix = np.zeros((5, 5), dtype=int)
    for record in records:
        matrix[int(record["stated_tier"]) - 1, int(record["final_tier"]) - 1] += 1
    fig, axis = plt.subplots(figsize=(7, 6))
    image = axis.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=axis, label="Profiles")
    axis.set_xticks(np.arange(5), [1, 2, 3, 4, 5])
    axis.set_yticks(np.arange(5), [1, 2, 3, 4, 5])
    axis.set_xlabel("Final tier")
    axis.set_ylabel("Stated tier")
    axis.set_title("Synthetic cohort: stated tier vs final tier")
    midpoint = matrix.max() / 2 if matrix.size else 0
    for stated_index in range(5):
        for final_index in range(5):
            count = int(matrix[stated_index, final_index])
            axis.text(
                final_index,
                stated_index,
                str(count),
                ha="center",
                va="center",
                color="white" if count > midpoint else "black",
            )
    fig.tight_layout()
    fig.savefig(output_path, dpi=int(ANALYSIS_CONFIG["heatmap_dpi"]))
    plt.close(fig)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _write_results(
    cohort_records: list[dict[str, Any]],
    demos: list[dict[str, Any]],
    cap_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    tie_rows: list[dict[str, Any]],
    count_matrix: list[dict[str, Any]],
    percent_matrix: list[dict[str, Any]],
    reduction_summary: list[dict[str, Any]],
    reduction_distribution: list[dict[str, Any]],
    sensitivity: list[dict[str, Any]],
    destination: Path,
) -> None:
    versions = {
        "Python": platform.python_version(),
        "NumPy": np.__version__,
        "Matplotlib": matplotlib.__version__,
        "Questionnaire": QUESTIONNAIRE_V2.version,
        "Capacity rule table": CAPACITY_RULE_TABLE_V1.version,
    }
    cohort_cap = next(row for row in cap_rows if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all")
    cohort_reduction = next(
        row
        for row in reduction_summary
        if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all"
    )
    cohort_components = [
        row
        for row in component_rows
        if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all"
    ]
    top_unique = max(cohort_components, key=lambda row: row["unique_binding_count"])
    tie_total = sum(
        row["profiles"]
        for row in tie_rows
        if row["dataset"] == "synthetic_cohort"
        and row["stratum"] == "all"
        and row["binding_type"] == "tied"
    )
    sensitivity_cohort = [row for row in sensitivity if row["dataset"] == "synthetic_cohort"]

    lines = [
        "# Ability binding analysis",
        "",
        "## Factual summary",
        "",
        f"- The saved synthetic cohort contains {len(cohort_records)} profiles; "
        f"{cohort_cap['capped_profiles']} ({cohort_cap['cap_rate']:.2%}) have stated tier above capacity.",
        f"- Among capped synthetic profiles, {top_unique['component_label']} is the most frequent unique binding component "
        f"({top_unique['unique_binding_count']} profiles); {tie_total} profiles have tied minimum capacity components.",
        f"- Mean reduction among capped synthetic profiles is {cohort_reduction['mean_reduction_when_capped']:.3f} tiers.",
        f"- For the one-at-a-time sensitivity scenarios, cap-rate changes range from "
        f"{min(row['cap_rate_change_percentage_points'] for row in sensitivity_cohort):.3f} to "
        f"{max(row['cap_rate_change_percentage_points'] for row in sensitivity_cohort):.3f} percentage points.",
        "- These statements describe the loaded cohort and the specified threshold perturbations; demo fixtures are reported separately below.",
        "",
        "## Cap application",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["Dataset", "Group", "Profiles", "Capped", "Cap rate"],
            [
                [
                    str(row["dataset"]),
                    str(row["stratum"]).replace("_", " "),
                    str(row["n_profiles"]),
                    str(row["capped_profiles"]),
                    f"{row['cap_rate']:.2%}",
                ]
                for row in cap_rows
            ],
        )
    )

    lines.extend(["", "## Binding components among capped profiles", ""])
    lines.append(
        "A unique binding count requires that exactly one applicable component has the minimum ceiling. "
        "A tied binding count includes the component when two or more applicable components share that minimum. "
        "Thus component-wise tied counts can refer to the same profile; tie combinations are listed separately."
    )
    lines.extend(
        _markdown_table(
            ["Dataset", "Group", "Component", "Unique", "Tied", "Any binding", "Capped denominator"],
            [
                [
                    str(row["dataset"]),
                    str(row["stratum"]).replace("_", " "),
                    str(row["component_label"]),
                    str(row["unique_binding_count"]),
                    str(row["tied_binding_count"]),
                    str(row["any_binding_count"]),
                    str(row["capped_profiles"]),
                ]
                for row in component_rows
            ],
        )
    )
    lines.extend(
        [
            "",
            "### Binding tie combinations",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            ["Dataset", "Group", "Binding component set", "Type", "Profiles"],
            [
                [
                    str(row["dataset"]),
                    str(row["stratum"]).replace("_", " "),
                    str(row["binding_component_set"]),
                    str(row["binding_type"]),
                    str(row["profiles"]),
                ]
                for row in tie_rows
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Stated-tier vs final-tier matrix: synthetic cohort",
            "",
            "Counts are shown first. Percentages are within each stated-tier row; empty stated-tier rows are all zero.",
            "",
            "### Counts",
            "",
        ]
    )
    matrix_headers = ["Stated tier", "Profiles", "Final 1", "Final 2", "Final 3", "Final 4", "Final 5"]
    cohort_count_rows = [row for row in count_matrix if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all"]
    lines.extend(
        _markdown_table(
            matrix_headers,
            [
                [
                    str(row["stated_tier"]),
                    str(row["row_profiles"]),
                    *(str(row[f"final_tier_{tier}"]) for tier in range(1, 6)),
                ]
                for row in cohort_count_rows
            ],
        )
    )
    lines.extend(["", "### Row percentages", ""])
    cohort_percent_rows = [
        row for row in percent_matrix if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all"
    ]
    lines.extend(
        _markdown_table(
            ["Stated tier", *(f"Final {tier}" for tier in range(1, 6))],
            [
                [
                    str(row["stated_tier"]),
                    *(f"{row[f'final_tier_{tier}_row_pct']:.2%}" for tier in range(1, 6)),
                ]
                for row in cohort_percent_rows
            ],
        )
    )
    lines.extend(
        [
            "",
            "![Stated tier versus final tier heatmap](./tier_matrix_heatmap.png)",
            "",
            "## Tier reduction when capped",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            ["Dataset", "Group", "Capped profiles", "Mean reduction"],
            [
                [
                    str(row["dataset"]),
                    str(row["stratum"]).replace("_", " "),
                    str(row["capped_profiles"]),
                    f"{row['mean_reduction_when_capped']:.3f}",
                ]
                for row in reduction_summary
            ],
        )
    )
    lines.extend(["", "### Reduction-size distribution (conditional on cap)", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Group", "Reduction (tiers)", "Profiles", "Share of capped"],
            [
                [
                    str(row["dataset"]),
                    str(row["stratum"]).replace("_", " "),
                    str(row["reduction_tiers"]),
                    str(row["profiles"]),
                    f"{row['share_of_capped']:.2%}",
                ]
                for row in reduction_distribution
            ],
        )
    )

    lines.extend(
        [
            "",
            "## One-at-a-time capacity-threshold sensitivity",
            "",
            "Every positive finite break in the buffer, EMI, and insurance bands, the required life-cover income multiple, "
            "and each income-stability tier ceiling is perturbed individually by -10% and +10%. Zero band endpoints remain zero "
            "under proportional perturbation and unbounded endpoints have no finite value to move. Adjacent band endpoints sharing "
            "a break move together to preserve continuity. For discrete stability ceilings, a reduction rounds down and an increase "
            "rounds up to an integer tier, constrained to the valid 1-5 tier range. Tier-distribution changes are percentage-point "
            "differences from the unmodified production table.",
            "",
        ]
    )
    sensitivity_rows = [row for row in sensitivity if row["dataset"] == "synthetic_cohort"]
    sensitivity_headers = [
        "Threshold scenario",
        "Base cap rate",
        "Scenario cap rate",
        "Cap-rate change (pp)",
        *(f"Tier {tier} share change (pp)" for tier in range(1, 6)),
    ]
    lines.extend(
        _markdown_table(
            sensitivity_headers,
            [
                [
                    str(row["scenario"]),
                    f"{row['baseline_cap_rate']:.2%}",
                    f"{row['scenario_cap_rate']:.2%}",
                    f"{row['cap_rate_change_percentage_points']:+.3f}",
                    *(f"{row[f'final_tier_{tier}_change_percentage_points']:+.3f}" for tier in range(1, 6)),
                ]
                for row in sensitivity_rows
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Demo data",
            "",
            "Demo rows are derived from static fixtures in the named seed scripts, not loaded from a live database. "
            "Monthly essential and other expenses are summed from seed entries; annual entries are prorated monthly. "
            "EMIs and life cover absent from a seed fixture are treated as zero, consistent with those scripts creating none. "
            "The showcase user's initial and post-bonus/EMI-closure risk attempts are separate snapshots.",
            "",
        ]
    )
    for demo in demos:
        lines.append(
            f"- `{demo['profile_id']}` source: `{demo['demo_source']}`; stated tier {demo['stated_tier']}, "
            f"capacity ceiling {demo['capacity_ceiling']}, final tier {demo['final_tier']}, "
            f"cap applied: {str(demo['cap_applied']).lower()}."
        )
    lines.extend(
        [
            "",
            "## Software and rule versions",
            "",
        ]
    )
    lines.extend(_markdown_table(["Component", "Version"], [[name, version] for name, version in versions.items()]))
    lines.extend(
        [
            "",
            "## Generated files",
            "",
            "- `binding_cap_rates.csv`",
            "- `binding_components.csv` and `binding_tie_combinations.csv`",
            "- `tier_matrix_counts.csv` and `tier_matrix_row_percentages.csv`",
            "- `tier_reduction_summary.csv` and `tier_reduction_distribution.csv`",
            "- `threshold_sensitivity.csv` and `threshold_sensitivity_tier_distribution.csv`",
            "- `tier_matrix_heatmap.png`",
            "- `binding_analysis_summary.json`",
            "",
        ]
    )
    destination.write_text("\n".join(lines), encoding="utf-8")


def run_analysis() -> dict[str, Path]:
    """Analyze the fixed cohort file and seed-script demo fixtures."""
    cohort = load_saved_cohort()
    cohort_records = _dataset_records(cohort)
    demos = _dataset_records(build_demo_profiles())
    records = cohort_records + demos

    cap_rows = _summarize_cap_rates(records)
    component_rows, tie_rows = _component_rows(records)
    count_matrix, percent_matrix = _tier_matrices(records)
    reduction_summary, reduction_distribution = _reduction_rows(records)
    sensitivity, sensitivity_tier_rows = _sensitivity_rows(records)

    output_dir = Path(ANALYSIS_CONFIG["results_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "cap_rates": output_dir / "binding_cap_rates.csv",
        "components": output_dir / "binding_components.csv",
        "tie_combinations": output_dir / "binding_tie_combinations.csv",
        "tier_counts": output_dir / "tier_matrix_counts.csv",
        "tier_percentages": output_dir / "tier_matrix_row_percentages.csv",
        "reduction_summary": output_dir / "tier_reduction_summary.csv",
        "reduction_distribution": output_dir / "tier_reduction_distribution.csv",
        "sensitivity": output_dir / "threshold_sensitivity.csv",
        "sensitivity_tiers": output_dir / "threshold_sensitivity_tier_distribution.csv",
        "heatmap": output_dir / "tier_matrix_heatmap.png",
        "json_summary": output_dir / "binding_analysis_summary.json",
        "report": output_dir / "results.md",
    }
    _write_csv(paths["cap_rates"], cap_rows)
    _write_csv(paths["components"], component_rows)
    _write_csv(paths["tie_combinations"], tie_rows)
    _write_csv(paths["tier_counts"], count_matrix)
    _write_csv(paths["tier_percentages"], percent_matrix)
    _write_csv(paths["reduction_summary"], reduction_summary)
    _write_csv(paths["reduction_distribution"], reduction_distribution)
    _write_csv(paths["sensitivity"], sensitivity)
    _write_csv(paths["sensitivity_tiers"], sensitivity_tier_rows)
    _plot_tier_heatmap(cohort_records, paths["heatmap"])

    versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "matplotlib": matplotlib.__version__,
        "questionnaire": QUESTIONNAIRE_V2.version,
        "capacity_rule_table": CAPACITY_RULE_TABLE_V1.version,
    }
    json_payload = {
        "input_cohort": str(ANALYSIS_CONFIG["cohort_csv"]),
        "cohort_profiles": len(cohort_records),
        "demo_sources": {record["profile_id"]: record["demo_source"] for record in demos},
        "software_versions": versions,
        "cap_rates": cap_rows,
        "binding_components": component_rows,
        "binding_tie_combinations": tie_rows,
        "tier_matrix_counts": count_matrix,
        "tier_matrix_row_percentages": percent_matrix,
        "tier_reduction_summary": reduction_summary,
        "tier_reduction_distribution": reduction_distribution,
        "threshold_sensitivity": sensitivity,
        "threshold_sensitivity_tier_distribution": sensitivity_tier_rows,
    }
    paths["json_summary"].write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    _write_results(
        cohort_records,
        demos,
        cap_rows,
        component_rows,
        tie_rows,
        count_matrix,
        percent_matrix,
        reduction_summary,
        reduction_distribution,
        sensitivity,
        paths["report"],
    )
    return paths


if __name__ == "__main__":
    for output_name, output_path in run_analysis().items():
        print(f"{output_name}: {output_path}")
