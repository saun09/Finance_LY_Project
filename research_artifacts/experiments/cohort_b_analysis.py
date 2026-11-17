"""Compare allocation methods over scenario and population-style cohorts."""

from __future__ import annotations

import csv
import json
import platform
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT, ROOT / "backend"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.services.allocation import compute_target_allocation
from app.services.allocation_config import CONFIG_VERSION
from app.services.asset_classification_config import AssetClass
from app.services.risk_profile import (
    IncomeStabilityValue,
    _find_band,
    compute_capacity_ceiling,
    compute_final_tier,
    compute_stated_tier,
)
from app.services.risk_profile_config import (
    CAPACITY_RULE_TABLE_V1,
    QUESTIONNAIRE_V2,
)
from research_artifacts.experiments.binding_analysis import (
    _threshold_values,
    perturb_capacity_threshold,
)
from research_artifacts.experiments.cohort_b import (
    COHORT_B_CONFIG,
    RESULTS_DIR,
    VARIANT_ORDER,
)
from research_artifacts.experiments.common import capacity_inputs_from_profile

OUT_DIR = RESULTS_DIR
SCENARIO_COHORT_PATH = ROOT / "research_artifacts" / "experiments" / "results" / "cohort.csv"

# Reproducibility settings for analyses, bootstrap intervals, and stress cases.
ANALYSIS_CONFIG: dict[str, Any] = {
    "seed": 20261110,
    "bootstrap_resamples": 2000,
    "bootstrap_seed": 20261111,
    "confidence_level": 0.95,
    "bootstrap_batch_size": 64,
    "income_loss_months": (3, 6),
    "equity_drawdowns": (0.20, 0.30, 0.40),
    "earner_death_years": 5,
    "debt_service_income_reduction": 0.30,
    "debt_service_months": 6,
    "threshold_perturbations": (-0.10, 0.10),
    "plot_dpi": 160,
}

BASE_METHODS = ("willingness_only", "ability_only")
ALPHAS = tuple(round(index / 10, 1) for index in range(11))
METHOD_ORDER = (
    *BASE_METHODS,
    *(f"blend_alpha_{alpha:.1f}" for alpha in ALPHAS),
    "gated_min",
)
METHOD_LABELS = {
    "willingness_only": "Willingness only",
    "ability_only": "Ability only",
    "gated_min": "Gated minimum",
    **{f"blend_alpha_{alpha:.1f}": f"Blend alpha={alpha:.1f}" for alpha in ALPHAS},
}
SCENARIOS: tuple[dict[str, Any], ...] = (
    *(
        {
            "scenario_id": f"S1_liquidity_{months}m",
            "scenario": "S1 liquidity",
            "months": months,
            "drawdown": 0.0,
        }
        for months in ANALYSIS_CONFIG["income_loss_months"]
    ),
    *(
        {
            "scenario_id": f"S2_total_liquid_{months}m_{int(drawdown * 100)}pct",
            "scenario": "S2 total-liquid",
            "months": months,
            "drawdown": drawdown,
        }
        for months in ANALYSIS_CONFIG["income_loss_months"]
        for drawdown in ANALYSIS_CONFIG["equity_drawdowns"]
    ),
    *(
        {
            "scenario_id": f"S3_earner_death_{int(drawdown * 100)}pct",
            "scenario": "S3 earner death",
            "months": 12 * int(ANALYSIS_CONFIG["earner_death_years"]),
            "drawdown": drawdown,
        }
        for drawdown in ANALYSIS_CONFIG["equity_drawdowns"]
    ),
    {
        "scenario_id": "S4_debt_service_shock",
        "scenario": "S4 debt-service shock",
        "months": int(ANALYSIS_CONFIG["debt_service_months"]),
        "drawdown": 0.0,
    },
)
POSTHOC_GROUPS = ("all", "willing_but_unable", "able_but_unwilling", "aligned")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"required cohort file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError(f"cohort file is empty: {path}")
    return rows


def _load_scenario_cohort() -> list[dict[str, Any]]:
    rows = _read_csv(SCENARIO_COHORT_PATH)
    int_fields = (
        "monthly_income",
        "essential_monthly_expense",
        "other_monthly_expense",
        "liquid_cash",
        "total_monthly_emi",
        "dependents_count",
        "total_life_cover",
        "investable_assets",
    )
    for row in rows:
        for key in int_fields:
            row[key] = int(float(row[key]))
        row["dataset"] = "scenario cohort"
        row["posthoc_group"] = "scenario cohort"
        row["stated_tier"], row["capacity_ceiling"] = _score(row)
    return rows


def _score(profile: dict[str, Any], rule_table=CAPACITY_RULE_TABLE_V1) -> tuple[int, int]:
    answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
    stated_tier = compute_stated_tier(answers, QUESTIONNAIRE_V2).tier
    ceiling = compute_capacity_ceiling(
        capacity_inputs_from_profile(profile),
        rule_table,
    ).ceiling
    return stated_tier, ceiling


def _load_population_cohort(variant: str) -> list[dict[str, Any]]:
    return _read_csv(RESULTS_DIR / f"cohort_b_{variant}.csv")


def _equity_shares() -> dict[int, float]:
    return {
        tier: float(compute_target_allocation(tier).target_pct[AssetClass.EQUITY] / 100)
        for tier in range(1, 6)
    }


def _method_tiers(profile: dict[str, Any]) -> dict[str, int]:
    stated = int(profile["stated_tier"])
    ceiling = int(profile["capacity_ceiling"])
    tiers = {
        "willingness_only": stated,
        "ability_only": ceiling,
        "gated_min": min(stated, ceiling),
    }
    for alpha in ALPHAS:
        tiers[f"blend_alpha_{alpha:.1f}"] = min(
            5,
            max(1, int(round(alpha * stated + (1 - alpha) * ceiling))),
        )
    return tiers


def _stress(profile: dict[str, Any], equity_share: float, scenario: dict[str, Any]) -> tuple[bool, float, bool]:
    income = float(profile["monthly_income"])
    essential = float(profile["essential_monthly_expense"])
    emi = float(profile["total_monthly_emi"])
    cash = float(profile["liquid_cash"])
    assets = float(profile["investable_assets"])
    cover = float(profile["total_life_cover"])
    dependents = int(profile["dependents_count"])
    scenario_id = str(scenario["scenario_id"])
    months = int(scenario["months"])
    drawdown = float(scenario["drawdown"])
    non_equity_liquid = cash + assets * (1 - equity_share)

    if scenario_id.startswith("S1_"):
        required = months * (essential + emi)
        available = non_equity_liquid
    elif scenario_id.startswith("S2_"):
        required = months * (essential + emi)
        available = non_equity_liquid + assets * equity_share * (1 - drawdown)
    elif scenario_id.startswith("S3_"):
        if dependents < 1:
            return False, 0.0, False
        required = (
            essential
            * 12
            * int(ANALYSIS_CONFIG["earner_death_years"])
        )
        available = (
            cover
            + cash
            + assets * (1 - equity_share)
            + assets * equity_share * (1 - drawdown)
        )
    elif scenario_id == "S4_debt_service_shock":
        reduced_income = income * (1 - float(ANALYSIS_CONFIG["debt_service_income_reduction"]))
        monthly_gap = max(0.0, essential + emi - reduced_income)
        required = months * monthly_gap
        available = non_equity_liquid
    else:
        raise ValueError(f"unknown stress scenario: {scenario_id}")

    shortfall = max(0.0, required - available)
    return shortfall > 0, shortfall, True


def _bootstrap_cis(values: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Bootstrap column means from a profile-by-metric matrix."""
    data = np.asarray(values, dtype=float)
    if data.ndim == 1:
        data = data[:, None]
    if data.shape[0] == 0:
        raise ValueError("bootstrap inputs must contain at least one profile")
    n_resamples = int(ANALYSIS_CONFIG["bootstrap_resamples"])
    means = np.empty((n_resamples, data.shape[1]), dtype=float)
    rng = np.random.default_rng(seed)
    batch_size = int(ANALYSIS_CONFIG["bootstrap_batch_size"])
    probabilities = np.full(data.shape[0], 1 / data.shape[0])
    for start in range(0, n_resamples, batch_size):
        stop = min(start + batch_size, n_resamples)
        weights = rng.multinomial(
            data.shape[0],
            probabilities,
            size=stop - start,
        )
        means[start:stop] = weights @ data / data.shape[0]
    tail = (1 - float(ANALYSIS_CONFIG["confidence_level"])) / 2
    return np.quantile(means, tail, axis=0), np.quantile(means, 1 - tail, axis=0)


def _apply_holm(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(range(len(rows)), key=lambda index: float(rows[index]["p_value"]))
    total = len(ordered)
    running_max = 0.0
    for rank, index in enumerate(ordered):
        adjusted = min(1.0, (total - rank) * float(rows[index]["p_value"]))
        running_max = max(running_max, adjusted)
        rows[index]["holm_p_value"] = running_max
        rows[index]["holm_family_size"] = total


def _binding_summary(
    profiles: list[dict[str, Any]],
    dataset: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    component_counts: dict[str, dict[str, int]] = {}
    reductions = {tier: 0 for tier in range(5)}
    capped = 0
    unique_binding_profiles = 0
    tied_binding_profiles = 0
    for profile in profiles:
        inputs = capacity_inputs_from_profile(profile)
        capacity = compute_capacity_ceiling(inputs)
        stated = int(profile["stated_tier"])
        reduction = stated - min(stated, capacity.ceiling)
        reductions[reduction] += 1
        if reduction <= 0:
            continue
        capped += 1
        applicable = [component for component in capacity.components if component.applicable]
        minimum = min(component.ceiling for component in applicable)
        binding = [
            component.name
            for component in applicable
            if component.ceiling == minimum
        ]
        if len(binding) == 1:
            unique_binding_profiles += 1
        else:
            tied_binding_profiles += 1
        for name in binding:
            counts = component_counts.setdefault(name, {"unique": 0, "tied": 0})
            counts["tied" if len(binding) > 1 else "unique"] += 1
    n = len(profiles)
    summary = {
        "dataset": dataset,
        "profiles": n,
        "capped_profiles": capped,
        "cap_rate": capped / n,
        "unique_binding_profiles": unique_binding_profiles,
        "tied_binding_profiles": tied_binding_profiles,
    }
    rows = [
        {
            "dataset": dataset,
            "component": name,
            "unique_binding_count": counts["unique"],
            "tied_binding_count": counts["tied"],
            "any_binding_count": counts["unique"] + counts["tied"],
            "unique_share_of_capped": counts["unique"] / capped if capped else 0.0,
            "tied_share_of_capped": counts["tied"] / capped if capped else 0.0,
        }
        for name, counts in sorted(component_counts.items())
    ]
    summary["tier_reduction_counts"] = {
        str(tier): count for tier, count in sorted(reductions.items())
    }
    return summary, rows


def _threshold_sensitivity(
    profiles: list[dict[str, Any]],
    dataset: str,
) -> list[dict[str, Any]]:
    scored = []
    for profile in profiles:
        inputs = capacity_inputs_from_profile(profile)
        capacity = compute_capacity_ceiling(inputs)
        answers = {question.id: str(profile[question.id]) for question in QUESTIONNAIRE_V2.questions}
        stated = compute_stated_tier(answers, QUESTIONNAIRE_V2).tier
        scored.append((inputs, stated, capacity))
    baseline_cap_rate = sum(
        stated > capacity.ceiling for _, stated, capacity in scored
    ) / len(scored)
    rows: list[dict[str, Any]] = []
    for field_name, label, threshold in _threshold_values(CAPACITY_RULE_TABLE_V1):
        for factor in ANALYSIS_CONFIG["threshold_perturbations"]:
            table = perturb_capacity_threshold(
                CAPACITY_RULE_TABLE_V1,
                field_name,
                threshold,
                factor,
            )
            cap_count = 0
            affected_component = {
                "buffer_months_bands": "buffer_months",
                "emi_to_income_bands": "emi_to_income_ratio",
                "insurance_coverage_bands": "insurance_adequacy",
                "required_life_cover_income_multiple": "insurance_adequacy",
                "irregular_income_ceiling": "income_stability",
                "regular_income_ceiling": "income_stability",
            }[field_name]
            for inputs, stated, capacity in scored:
                components = {
                    component.name: component
                    for component in capacity.components
                    if component.applicable
                }
                other_ceiling = min(
                    component.ceiling
                    for name, component in components.items()
                    if name != affected_component
                )
                if affected_component == "buffer_months":
                    changed_ceiling = _find_band(
                        inputs.buffer_coverage_months,
                        table.buffer_months_bands,
                    ).ceiling
                elif affected_component == "emi_to_income_ratio":
                    changed_ceiling = _find_band(
                        inputs.emi_to_income_ratio,
                        table.emi_to_income_bands,
                    ).ceiling
                elif affected_component == "insurance_adequacy":
                    if inputs.dependents_count <= 0:
                        changed_ceiling = 5
                    else:
                        required_cover = (
                            inputs.monthly_income_paise
                            * 12
                            * table.required_life_cover_income_multiple
                        )
                        coverage_ratio = (
                            Decimal(inputs.total_life_cover_paise)
                            / Decimal(required_cover)
                            if required_cover > 0
                            else Decimal(0)
                        )
                        changed_ceiling = _find_band(
                            coverage_ratio,
                            table.insurance_coverage_bands,
                        ).ceiling
                else:
                    changed_ceiling = (
                        table.regular_income_ceiling
                        if inputs.income_stability == IncomeStabilityValue.REGULAR
                        else table.irregular_income_ceiling
                    )
                cap_count += stated > min(other_ceiling, changed_ceiling)
            rate = cap_count / len(scored)
            rows.append(
                {
                    "dataset": dataset,
                    "threshold_name": label,
                    "threshold_field": field_name,
                    "base_threshold": threshold,
                    "perturbation": factor,
                    "baseline_cap_rate": baseline_cap_rate,
                    "scenario_cap_rate": rate,
                    "cap_rate_change_percentage_points": (rate - baseline_cap_rate) * 100,
                    "moves_cap_rate": rate != baseline_cap_rate,
                }
            )
    return rows


def _dataset_evaluation(
    profiles: list[dict[str, Any]],
    dataset: str,
    equity_shares: dict[int, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tiers = np.asarray([[_method_tiers(profile)[method] for method in METHOD_ORDER] for profile in profiles])
    stated = np.asarray([int(profile["stated_tier"]) for profile in profiles])
    ceiling = np.asarray([int(profile["capacity_ceiling"]) for profile in profiles])
    group_names = np.asarray([str(profile.get("posthoc_group", "aligned")) for profile in profiles])
    preference_rows: list[dict[str, Any]] = []
    for group_index, group in enumerate(POSTHOC_GROUPS):
        selected = np.ones(len(profiles), dtype=bool) if group == "all" else group_names == group
        if not np.any(selected):
            continue
        assignments = tiers[selected]
        stated_selected = stated[selected, None]
        best_allowed = np.minimum(stated_selected, ceiling[selected, None])
        preference_values = np.concatenate(
            [
                (assignments > stated_selected).astype(float),
                (assignments < best_allowed).astype(float),
                assignments.astype(float) - stated_selected,
                np.abs(assignments.astype(float) - stated_selected),
            ],
            axis=1,
        )
        lower, upper = _bootstrap_cis(
            preference_values,
            int(ANALYSIS_CONFIG["bootstrap_seed"]) + group_index,
        )
        metric_names = (
            "over_risk_rate",
            "unnecessary_conservatism_rate",
            "mean_signed_tier_gap_to_stated",
            "mean_absolute_tier_gap_to_stated",
        )
        columns = len(METHOD_ORDER)
        for method_index, method in enumerate(METHOD_ORDER):
            values = (
                float(preference_values[:, method_index].mean()),
                float(preference_values[:, columns + method_index].mean()),
                float(preference_values[:, 2 * columns + method_index].mean()),
                float(preference_values[:, 3 * columns + method_index].mean()),
            )
            for metric_index, metric in enumerate(metric_names):
                preference_rows.append(
                    {
                        "dataset": dataset,
                        "posthoc_group": group,
                        "method": method,
                        "metric": metric,
                        "estimate": values[metric_index],
                        "ci95_low": float(lower[metric_index * columns + method_index]),
                        "ci95_high": float(upper[metric_index * columns + method_index]),
                        "n_profiles": int(np.sum(selected)),
                    }
                )

    violation_rows: list[dict[str, Any]] = []
    mcnemar_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    floor_rows: list[dict[str, Any]] = []
    all_test_rows: list[dict[str, Any]] = []
    for scenario_index, scenario in enumerate(SCENARIOS):
        eligible = np.asarray(
            [
                int(profile["dependents_count"]) >= 1
                if str(scenario["scenario_id"]).startswith("S3_")
                else True
                for profile in profiles
            ],
            dtype=bool,
        )
        chosen = np.flatnonzero(eligible)
        if not len(chosen):
            raise ValueError(f"scenario has no eligible profiles: {scenario['scenario_id']}")
        viol = np.zeros((len(profiles), len(METHOD_ORDER)), dtype=float)
        shortfalls = np.zeros_like(viol)
        for profile_index, profile in enumerate(profiles):
            for method_index, method in enumerate(METHOD_ORDER):
                tier = int(tiers[profile_index, method_index])
                is_violation, shortfall, _ = _stress(
                    profile,
                    equity_shares[tier],
                    scenario,
                )
                viol[profile_index, method_index] = float(is_violation)
                shortfalls[profile_index, method_index] = shortfall
        selected_violations = viol[chosen]
        floor_violations = np.asarray(
            [
                _stress(profile, equity_shares[1], scenario)[0]
                for profile in profiles
            ],
            dtype=bool,
        )[chosen]
        floor_metric_values = np.column_stack(
            [
                selected_violations,
                np.repeat(floor_violations[:, None], len(METHOD_ORDER), axis=1),
                np.repeat(floor_violations[:, None], len(METHOD_ORDER), axis=1),
                selected_violations * (~floor_violations)[:, None],
            ]
        )
        scenario_ci_low, scenario_ci_high = _bootstrap_cis(
            np.column_stack((selected_violations, shortfalls[chosen], floor_metric_values)),
            int(ANALYSIS_CONFIG["bootstrap_seed"]) + 300 + scenario_index,
        )
        method_count = len(METHOD_ORDER)
        for method_index, method in enumerate(METHOD_ORDER):
            method_violation = selected_violations[:, method_index].astype(bool)
            unavoidable = floor_violations
            avoidable = method_violation & ~floor_violations
            common = {
                "dataset": dataset,
                "scenario_id": scenario["scenario_id"],
                "scenario": scenario["scenario"],
                "method": method,
                "n_profiles": len(chosen),
                "violation_rate": float(method_violation.mean()),
                "violation_rate_ci95_low": float(scenario_ci_low[method_index]),
                "violation_rate_ci95_high": float(scenario_ci_high[method_index]),
                "mean_shortfall_rupees": float(shortfalls[chosen, method_index].mean()),
                "mean_shortfall_rupees_ci95_low": float(scenario_ci_low[method_count + method_index]),
                "mean_shortfall_rupees_ci95_high": float(scenario_ci_high[method_count + method_index]),
            }
            violation_rows.append(common)
            floor_rows.append(
                {
                    **common,
                    "floor_violation_rate": float(floor_violations.mean()),
                    "floor_violation_rate_ci95_low": float(scenario_ci_low[3 * method_count + method_index]),
                    "floor_violation_rate_ci95_high": float(scenario_ci_high[3 * method_count + method_index]),
                    "unavoidable_violation_rate": float(unavoidable.mean()),
                    "unavoidable_violation_rate_ci95_low": float(scenario_ci_low[4 * method_count + method_index]),
                    "unavoidable_violation_rate_ci95_high": float(scenario_ci_high[4 * method_count + method_index]),
                    "avoidable_violation_rate": float(avoidable.mean()),
                    "avoidable_violation_rate_ci95_low": float(scenario_ci_low[5 * method_count + method_index]),
                    "avoidable_violation_rate_ci95_high": float(scenario_ci_high[5 * method_count + method_index]),
                    "unavoidable_count": int(unavoidable.sum()),
                    "avoidable_count": int(avoidable.sum()),
                }
            )
            if method == "gated_min":
                continue
            gated_index = METHOD_ORDER.index("gated_min")
            gated_violates_only = int(
                np.sum(
                    selected_violations[:, gated_index].astype(bool)
                    & ~method_violation
                )
            )
            comparator_violates_only = int(
                np.sum(
                    ~selected_violations[:, gated_index].astype(bool)
                    & method_violation
                )
            )
            discordant = gated_violates_only + comparator_violates_only
            p_value = (
                float(
                    binomtest(
                        gated_violates_only,
                        discordant,
                        p=0.5,
                        alternative="two-sided",
                    ).pvalue
                )
                if discordant
                else 1.0
            )
            mcnemar_rows.append(
                {
                    "dataset": dataset,
                    "scenario_id": scenario["scenario_id"],
                    "comparator": method,
                    "gated_violates_only": gated_violates_only,
                    "comparator_violates_only": comparator_violates_only,
                    "discordant_pairs": discordant,
                    "p_value": p_value,
                }
            )

        applicable_ablations = (
            ("S1_", "no_buffer_component"),
            ("S1_", "no_income_stability"),
            ("S2_", "no_buffer_component"),
            ("S3_", "no_insurance_component"),
            ("S4_", "no_emi_component"),
        )
        action_names = [
            action
            for prefix, action in applicable_ablations
            if str(scenario["scenario_id"]).startswith(prefix)
        ]
        ablation_entries: list[dict[str, Any]] = []
        ablation_ci_columns: list[np.ndarray] = []
        for action in action_names:
            ablated_violations: list[float] = []
            for profile_index, profile in enumerate(profiles):
                inputs = capacity_inputs_from_profile(profile)
                if action == "no_buffer_component":
                    inputs = replace(inputs, buffer_coverage_months=inputs.buffer_coverage_months + 1_000)
                elif action == "no_income_stability":
                    inputs = replace(inputs, income_stability=IncomeStabilityValue.REGULAR)
                elif action == "no_insurance_component":
                    inputs = replace(inputs, dependents_count=0)
                elif action == "no_emi_component":
                    inputs = replace(inputs, emi_to_income_ratio=0, total_monthly_emi_paise=0)
                else:
                    raise ValueError(f"unknown ablation: {action}")
                stated_tier = int(profile["stated_tier"])
                ablated_ceiling = compute_capacity_ceiling(inputs).ceiling
                ablated_tier = min(stated_tier, ablated_ceiling)
                violated, _, included = _stress(
                    profile,
                    equity_shares[ablated_tier],
                    scenario,
                )
                ablated_violations.append(float(violated and included))
            ablated = np.asarray(ablated_violations, dtype=float)[chosen]
            compare_indices = (
                METHOD_ORDER.index("gated_min"),
                METHOD_ORDER.index("willingness_only"),
            )
            for comparator_index in compare_indices:
                comparator = METHOD_ORDER[comparator_index]
                comparator_values = selected_violations[:, comparator_index]
                differences = ablated - comparator_values
                ablation_entries.append(
                    {
                        "dataset": dataset,
                        "scenario_id": scenario["scenario_id"],
                        "ablation": action,
                        "comparator": comparator,
                        "ablated_violation_rate": float(ablated.mean()),
                        "comparator_violation_rate": float(comparator_values.mean()),
                        "paired_rate_difference": float(differences.mean()),
                        "n_profiles": len(chosen),
                    }
                )
                ablation_ci_columns.extend((ablated, comparator_values, differences))
        if ablation_entries:
            ablation_low, ablation_high = _bootstrap_cis(
                np.column_stack(ablation_ci_columns),
                int(ANALYSIS_CONFIG["bootstrap_seed"]) + 500 + scenario_index,
            )
            for entry_index, entry in enumerate(ablation_entries):
                offset = 3 * entry_index
                ablation_rows.append(
                    {
                        **entry,
                        "ablated_ci95_low": float(ablation_low[offset]),
                        "ablated_ci95_high": float(ablation_high[offset]),
                        "difference_ci95_low": float(ablation_low[offset + 2]),
                        "difference_ci95_high": float(ablation_high[offset + 2]),
                    }
                )
    return violation_rows, preference_rows, mcnemar_rows, ablation_rows, {
        "floor_rows": floor_rows,
        "tiers": tiers,
        "profile_rows": profiles,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite previous results file: {path}")
    if not rows:
        raise ValueError(f"refusing to write an empty results file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot_violations(rows: list[dict[str, Any]], dataset: str, output: Path) -> None:
    selected = [row for row in rows if row["dataset"] == dataset]
    scenario_ids = list(dict.fromkeys(row["scenario_id"] for row in selected))
    methods = list(METHOD_ORDER)
    matrix = np.asarray(
        [
            [
                next(
                    row["violation_rate"]
                    for row in selected
                    if row["scenario_id"] == scenario_id and row["method"] == method
                )
                for scenario_id in scenario_ids
            ]
            for method in methods
        ]
    )
    fig, axis = plt.subplots(figsize=(max(12, len(scenario_ids)), 8))
    image = axis.imshow(matrix, aspect="auto", vmin=0, vmax=1, cmap="viridis")
    axis.set_xticks(np.arange(len(scenario_ids)), scenario_ids, rotation=40, ha="right")
    axis.set_yticks(np.arange(len(methods)), [METHOD_LABELS[item] for item in methods])
    axis.set_title(f"Violation rates: {dataset}")
    fig.colorbar(image, ax=axis, label="Violation rate")
    fig.tight_layout()
    fig.savefig(output, dpi=int(ANALYSIS_CONFIG["plot_dpi"]))
    plt.close(fig)


def _plot_frontier(
    frontier_rows: list[dict[str, Any]],
    output: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(9, 7))
    for dataset in dict.fromkeys(row["dataset"] for row in frontier_rows):
        selected = [row for row in frontier_rows if row["dataset"] == dataset]
        axis.plot(
            [row["expected_equity_share"] for row in selected],
            [row["violation_rate"] for row in selected],
            marker="o",
            label=dataset,
        )
        for row in selected:
            axis.annotate(
                f'{row["alpha_on_stated_tier"]:.1f}',
                (row["expected_equity_share"], row["violation_rate"]),
                fontsize=7,
            )
    axis.set_xlabel("Expected equity share")
    axis.set_ylabel("S1 3-month liquidity violation rate")
    axis.set_title("Blend alpha sweep: expected equity share vs violation rate")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=7, ncol=2)
    figure.tight_layout()
    figure.savefig(output, dpi=int(ANALYSIS_CONFIG["plot_dpi"]))
    plt.close(figure)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return lines


def _fmt(value: float) -> str:
    return f"{100 * value:.2f}%"


def _write_report(
    path: Path,
    datasets: list[str],
    prevalence_rows: list[dict[str, Any]],
    violation_rows: list[dict[str, Any]],
    preference_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    floor_rows: list[dict[str, Any]],
    binding_summaries: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    sensitivity_rows: list[dict[str, Any]],
    mcnemar_rows: list[dict[str, Any]],
    frontier_rows: list[dict[str, Any]],
    versions: dict[str, str],
    plots: list[Path],
) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite previous report: {path}")
    lines = [
        "# Cohort B results",
        "",
        "Data source: SOURCE_TO_FILL.",
        "",
        "## Cohorts and reproducibility",
        "",
    ]
    cohort_rows = [
        [
            item["dataset"],
            item["posthoc_group"],
            f'{_fmt(item["prevalence"])} ({item["count"]})',
        ]
        for item in prevalence_rows
    ]
    cohort_rows.insert(
        0,
        [
            "scenario cohort",
            "designed strata (prevalence by design)",
            str(next(row["profiles"] for row in binding_summaries if row["dataset"] == "scenario cohort")),
        ],
    )
    lines.extend(_markdown_table(["Dataset", "Group", "Prevalence (N)"], cohort_rows))
    lines.extend(["", "## Violation rate by method and scenario", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Scenario", "Method", "Violation rate (95% CI)", "Mean shortfall (Rs, 95% CI)"],
            [
                [
                    row["dataset"],
                    row["scenario_id"],
                    METHOD_LABELS[row["method"]],
                    f'{_fmt(row["violation_rate"])} [{_fmt(row["violation_rate_ci95_low"])}, {_fmt(row["violation_rate_ci95_high"])}]',
                    f'{row["mean_shortfall_rupees"]:.2f} [{row["mean_shortfall_rupees_ci95_low"]:.2f}, {row["mean_shortfall_rupees_ci95_high"]:.2f}]',
                ]
                for row in violation_rows
            ],
        )
    )
    lines.extend(["", "## Blend alpha sweep", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Alpha on stated tier", "Scenario", "Violation rate", "Expected equity share"],
            [
                [
                    row["dataset"],
                    f'{row["alpha_on_stated_tier"]:.1f}',
                    row["scenario_id"],
                    f'{_fmt(row["violation_rate"])} [{_fmt(row["violation_rate_ci95_low"])}, {_fmt(row["violation_rate_ci95_high"])}]',
                    f'{row["expected_equity_share"]:.6f} [{row["expected_equity_share_ci95_low"]:.6f}, {row["expected_equity_share_ci95_high"]:.6f}]',
                ]
                for row in frontier_rows
            ],
        )
    )
    # Expected share is calculated from generated profile tiers and is also
    # exported in the frontier table by the analysis driver.
    lines.extend(["", "## Preference metrics by post-hoc group", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Post-hoc group", "Method", "Metric", "Estimate (95% CI)", "N"],
            [
                [
                    row["dataset"],
                    row["posthoc_group"],
                    METHOD_LABELS[row["method"]],
                    row["metric"],
                    f'{row["estimate"]:.6f} [{row["ci95_low"]:.6f}, {row["ci95_high"]:.6f}]',
                    row["n_profiles"],
                ]
                for row in preference_rows
            ],
        )
    )
    lines.extend(["", "## Ablations", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Scenario", "Ablation", "Compared with", "Ablated rate (95% CI)", "Rate difference"],
            [
                [
                    row["dataset"],
                    row["scenario_id"],
                    row["ablation"],
                    METHOD_LABELS[row["comparator"]],
                    f'{_fmt(row["ablated_violation_rate"])} [{_fmt(row["ablated_ci95_low"])}, {_fmt(row["ablated_ci95_high"])}]',
                    f'{_fmt(row["paired_rate_difference"])} [{_fmt(row["difference_ci95_low"])}, {_fmt(row["difference_ci95_high"])}]',
                ]
                for row in ablation_rows
            ],
        )
    )
    lines.extend(["", "## Avoidable and unavoidable violations", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Scenario", "Method", "Tier-1 floor rate (95% CI)", "Unavoidable rate (95% CI)", "Avoidable rate (95% CI)", "Unavoidable N", "Avoidable N"],
            [
                [
                    row["dataset"],
                    row["scenario_id"],
                    METHOD_LABELS[row["method"]],
                    f'{_fmt(row["floor_violation_rate"])} [{_fmt(row["floor_violation_rate_ci95_low"])}, {_fmt(row["floor_violation_rate_ci95_high"])}]',
                    f'{_fmt(row["unavoidable_violation_rate"])} [{_fmt(row["unavoidable_violation_rate_ci95_low"])}, {_fmt(row["unavoidable_violation_rate_ci95_high"])}]',
                    f'{_fmt(row["avoidable_violation_rate"])} [{_fmt(row["avoidable_violation_rate_ci95_low"])}, {_fmt(row["avoidable_violation_rate_ci95_high"])}]',
                    row["unavoidable_count"],
                    row["avoidable_count"],
                ]
                for row in floor_rows
            ],
        )
    )
    lines.extend(["", "## Binding analysis", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Profiles", "Capped", "Cap rate", "Unique binding profiles", "Tied binding profiles", "Tier reduction counts"],
            [
                [
                    row["dataset"],
                    row["profiles"],
                    row["capped_profiles"],
                    _fmt(row["cap_rate"]),
                    row["unique_binding_profiles"],
                    row["tied_binding_profiles"],
                    json.dumps(row["tier_reduction_counts"], separators=(",", ":")),
                ]
                for row in binding_summaries
            ],
        )
    )
    lines.extend(["", "### Binding components", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Component", "Unique", "Tied", "Any"],
            [
                [row["dataset"], row["component"], row["unique_binding_count"], row["tied_binding_count"], row["any_binding_count"]]
                for row in component_rows
            ],
        )
    )
    lines.extend(["", "## Threshold sensitivity (+/-10%)", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Threshold", "Perturbation", "Baseline cap rate", "Changed cap rate", "Change (percentage points)", "Moved cap rate"],
            [
                [
                    row["dataset"],
                    f'{row["threshold_name"]} ({row["base_threshold"]})',
                    f'{row["perturbation"]:+.0%}',
                    _fmt(row["baseline_cap_rate"]),
                    _fmt(row["scenario_cap_rate"]),
                    f'{row["cap_rate_change_percentage_points"]:.4f}',
                    row["moves_cap_rate"],
                ]
                for row in sensitivity_rows
            ],
        )
    )
    moved_thresholds = [
        [
            dataset,
            row["threshold_name"],
            f'{row["perturbation"]:+.0%}',
            _fmt(row["baseline_cap_rate"]),
            _fmt(row["scenario_cap_rate"]),
        ]
        for dataset in datasets
        for row in sensitivity_rows
        if row["dataset"] == dataset and row["moves_cap_rate"]
    ]
    lines.extend(["", "### Thresholds with changed cap rate", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Threshold", "Perturbation", "Baseline cap rate", "Changed cap rate"],
            moved_thresholds,
        )
    )
    lines.extend(["", "## Paired McNemar tests", ""])
    lines.extend(
        _markdown_table(
            ["Dataset", "Scenario", "Comparator", "Gated only", "Comparator only", "Discordant", "Exact p", "Holm-adjusted p"],
            [
                [
                    row["dataset"],
                    row["scenario_id"],
                    METHOD_LABELS[row["comparator"]],
                    row["gated_violates_only"],
                    row["comparator_violates_only"],
                    row["discordant_pairs"],
                    f'{row["p_value"]:.8g}',
                    f'{row["holm_p_value"]:.8g}',
                ]
                for row in mcnemar_rows
            ],
        )
    )
    lines.extend(["", "## Plots", ""])
    lines.extend(f"- `{plot.name}`" for plot in plots)
    lines.extend(
        [
            "",
            "## Threats to validity",
            "",
            "- cohort_b distribution parameters are assumptions until their SOURCE_TO_FILL fields are replaced with documented sources.",
            "- Results are synthetic scenario calculations and do not estimate population rates.",
            "- The scenario cohort retains its designed strata; its label in these outputs is `scenario cohort`.",
            "- Stress outcomes use plain cash-flow arithmetic and do not call the capacity rule table.",
            "",
            "## Runtime versions",
            "",
        ]
    )
    lines.extend(
        [
            "",
            "### Cohort B parameters",
            "",
            "```json",
            json.dumps(COHORT_B_CONFIG, indent=2, default=str),
            "```",
            "",
        ]
    )
    lines.extend(_markdown_table(["Library", "Version"], [[key, value] for key, value in versions.items()]))
    lines.extend(["", "## Reproduction commands", "", "```powershell"])
    lines.extend(
        [
            "python research_artifacts\\experiments\\cohort_b.py",
            "python research_artifacts\\experiments\\cohort_b_analysis.py",
        ]
    )
    lines.extend(["```", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_analysis() -> dict[str, Path]:
    target_paths = [
        OUT_DIR / "cohort_b_results.md",
        OUT_DIR / "cohort_b_violations.csv",
        OUT_DIR / "cohort_b_preference_metrics.csv",
        OUT_DIR / "cohort_b_ablation_results.csv",
        OUT_DIR / "cohort_b_avoidable_unavoidable.csv",
        OUT_DIR / "cohort_b_mcnemar_tests.csv",
        OUT_DIR / "cohort_b_binding_summary.csv",
        OUT_DIR / "cohort_b_binding_components.csv",
        OUT_DIR / "cohort_b_threshold_sensitivity.csv",
        OUT_DIR / "cohort_b_alpha_frontier.csv",
        OUT_DIR / "cohort_b_analysis.json",
        OUT_DIR / "cohort_b_alpha_frontier.png",
        *(OUT_DIR / f"cohort_b_violations_{name.replace(' ', '_')}.png" for name in ("scenario cohort", *VARIANT_ORDER)),
    ]
    existing = [path for path in target_paths if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing cohort B outputs: "
            + ", ".join(str(path) for path in existing)
        )
    datasets: list[tuple[str, list[dict[str, Any]]]] = [
        ("scenario cohort", _load_scenario_cohort()),
        *((variant, _load_population_cohort(variant)) for variant in VARIANT_ORDER),
    ]
    equity_shares = _equity_shares()
    violation_rows: list[dict[str, Any]] = []
    preference_rows: list[dict[str, Any]] = []
    mcnemar_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []
    floor_rows: list[dict[str, Any]] = []
    binding_summaries: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    prevalence_rows: list[dict[str, Any]] = []
    tier_data: dict[str, dict[str, Any]] = {}
    for dataset_index, (dataset, profiles) in enumerate(datasets):
        rows, preferences, tests, ablations, extra = _dataset_evaluation(
            profiles,
            dataset,
            equity_shares,
        )
        violation_rows.extend(rows)
        preference_rows.extend(preferences)
        mcnemar_rows.extend(tests)
        ablation_rows.extend(ablations)
        floor_rows.extend(extra["floor_rows"])
        tier_data[dataset] = extra
        if dataset != "scenario cohort":
            group_counts = {
                group: sum(profile["posthoc_group"] == group for profile in profiles)
                for group in ("willing_but_unable", "able_but_unwilling", "aligned")
            }
            prevalence_rows.extend(
                {
                    "dataset": dataset,
                    "posthoc_group": group,
                    "count": count,
                    "prevalence": count / len(profiles),
                }
                for group, count in group_counts.items()
            )
        summary, components = _binding_summary(profiles, dataset)
        binding_summaries.append(summary)
        component_rows.extend(components)
        sensitivity_rows.extend(_threshold_sensitivity(profiles, dataset))
        print(
            f"analyzed {dataset}: profiles={len(profiles)}, "
            f"violations={len(rows)}, preference_rows={len(preferences)}"
        )
    _apply_holm(mcnemar_rows)

    frontier_rows: list[dict[str, Any]] = []
    for dataset, profiles in datasets:
        stated = np.asarray([int(profile["stated_tier"]) for profile in profiles])
        ceiling = np.asarray([int(profile["capacity_ceiling"]) for profile in profiles])
        s1_scenario = next(
            scenario for scenario in SCENARIOS
            if scenario["scenario_id"] == "S1_liquidity_3m"
        )
        frontier_data: list[dict[str, Any]] = []
        frontier_ci_columns: list[np.ndarray] = []
        for alpha in ALPHAS:
            assigned = np.rint(alpha * stated + (1 - alpha) * ceiling).astype(int).clip(1, 5)
            outcomes = np.asarray(
                [
                    _stress(profile, equity_shares[int(tier)], s1_scenario)[0]
                    for profile, tier in zip(profiles, assigned)
                ],
                dtype=float,
            )
            equity = np.asarray(
                [equity_shares[int(tier)] for tier in assigned],
                dtype=float,
            )
            frontier_data.append(
                {
                    "dataset": dataset,
                    "alpha_on_stated_tier": alpha,
                    "scenario_id": s1_scenario["scenario_id"],
                    "violation_rate": float(outcomes.mean()),
                    "expected_equity_share": float(equity.mean()),
                }
            )
            frontier_ci_columns.extend((outcomes, equity))
        frontier_low, frontier_high = _bootstrap_cis(
            np.column_stack(frontier_ci_columns),
            int(ANALYSIS_CONFIG["bootstrap_seed"]) + len(frontier_rows),
        )
        for alpha_index, row in enumerate(frontier_data):
            offset = 2 * alpha_index
            frontier_rows.append(
                {
                    **row,
                    "violation_rate_ci95_low": float(frontier_low[offset]),
                    "violation_rate_ci95_high": float(frontier_high[offset]),
                    "expected_equity_share_ci95_low": float(frontier_low[offset + 1]),
                    "expected_equity_share_ci95_high": float(frontier_high[offset + 1]),
                }
            )

    versions = {
        "Python": platform.python_version(),
        "NumPy": np.__version__,
        "SciPy": scipy.__version__,
        "Matplotlib": matplotlib.__version__,
        "Questionnaire": QUESTIONNAIRE_V2.version,
        "Capacity rule table": CAPACITY_RULE_TABLE_V1.version,
        "Allocation configuration": CONFIG_VERSION,
    }
    output_paths: dict[str, Path] = {}
    tables = (
        ("violations", violation_rows),
        ("preference_metrics", preference_rows),
        ("ablation_results", ablation_rows),
        ("avoidable_unavoidable", floor_rows),
        ("mcnemar_tests", mcnemar_rows),
        ("binding_summary", binding_summaries),
        ("binding_components", component_rows),
        ("threshold_sensitivity", sensitivity_rows),
        ("alpha_frontier", frontier_rows),
    )
    for name, rows in tables:
        path = OUT_DIR / f"cohort_b_{name}.csv"
        _write_csv(path, rows)
        output_paths[name] = path

    plot_paths = []
    for dataset, _ in datasets:
        path = OUT_DIR / f"cohort_b_violations_{dataset.replace(' ', '_')}.png"
        _plot_violations(violation_rows, dataset, path)
        plot_paths.append(path)
    frontier_plot = OUT_DIR / "cohort_b_alpha_frontier.png"
    _plot_frontier(
        frontier_rows,
        frontier_plot,
    )
    plot_paths.append(frontier_plot)

    report_path = OUT_DIR / "cohort_b_results.md"
    _write_report(
        report_path,
        [dataset for dataset, _ in datasets],
        prevalence_rows,
        violation_rows,
        preference_rows,
        ablation_rows,
        floor_rows,
        binding_summaries,
        component_rows,
        sensitivity_rows,
        mcnemar_rows,
        frontier_rows,
        versions,
        plot_paths,
    )
    summary_path = OUT_DIR / "cohort_b_analysis.json"
    summary_path.write_text(
        json.dumps(
            {
                "analysis_config": ANALYSIS_CONFIG,
                "cohort_config": COHORT_B_CONFIG,
                "versions": versions,
                "dataset_sizes": {name: len(rows) for name, rows in datasets},
                "posthoc_prevalence": prevalence_rows,
                "violation_rows": violation_rows,
                "preference_rows": preference_rows,
                "ablation_rows": ablation_rows,
                "floor_rows": floor_rows,
                "mcnemar_rows": mcnemar_rows,
                "binding_summaries": binding_summaries,
                "binding_component_rows": component_rows,
                "threshold_sensitivity": sensitivity_rows,
                "alpha_frontier": frontier_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths.update(
        {
            "report": report_path,
            "summary": summary_path,
            "alpha_frontier_plot": frontier_plot,
            **{f"plot_{index}": path for index, path in enumerate(plot_paths, start=1)},
        }
    )
    print(
        json.dumps(
            {
                "versions": versions,
                "dataset_sizes": {name: len(rows) for name, rows in datasets},
                "posthoc_prevalence": {
                    name: {
                        group: sum(row.get("posthoc_group") == group for row in rows) / len(rows)
                        for group in ("willing_but_unable", "able_but_unwilling", "aligned")
                    }
                    for name, rows in datasets
                    if name != "scenario cohort"
                },
                "thresholds_moving_cap_rate": {
                    name: sorted(
                        {
                            row["threshold_name"]
                            for row in sensitivity_rows
                            if row["dataset"] == name and row["moves_cap_rate"]
                        }
                    )
                    for name, _ in datasets
                },
                "outputs": {name: str(path) for name, path in output_paths.items()},
            },
            indent=2,
        )
    )
    return output_paths


if __name__ == "__main__":
    run_analysis()
