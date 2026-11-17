"""Run capacity-first fragility experiments and generate all reported outputs."""

from __future__ import annotations

import json
import platform
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy
from scipy.stats import binomtest

from app.services.allocation import compute_target_allocation
from app.services.allocation_config import CONFIG_VERSION
from app.services.asset_classification_config import AssetClass
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1, QUESTIONNAIRE_V2

from research_artifacts.experiments.cohort import (
    COHORT_CONFIG,
    RESULTS_DIR,
    STRATUM_ORDER,
    __doc__ as COHORT_DISTRIBUTION_DOCUMENTATION,
    generate_cohort,
    save_cohort,
)
from research_artifacts.experiments.common import compute_method_tiers


# All stress, inference, and output parameters live in this block.
EXPERIMENT_CONFIG: dict[str, Any] = {
    "main_scenario": {"equity_drawdown": 0.30, "income_loss_months": 3},
    "sensitivity_equity_drawdowns": (0.20, 0.30, 0.40),
    "sensitivity_income_loss_months": (3, 6),
    "bootstrap_resamples": 2000,
    "bootstrap_seed": 20261107,
    "confidence_level": 0.95,
    "bootstrap_batch_size": 128,
}

METHODS = (
    "willingness_only",
    "ability_only",
    "blend",
    "gated_min",
    "gated_min_no_insurance",
    "gated_min_no_emi",
)
METHOD_LABELS = {
    "willingness_only": "Willingness only",
    "ability_only": "Ability only",
    "blend": "50/50 blend",
    "gated_min": "Gated minimum",
    "gated_min_no_insurance": "No-insurance ablation",
    "gated_min_no_emi": "No-EMI ablation",
}


@lru_cache(maxsize=5)
def equity_share_for_tier(tier: int) -> float:
    """Read the production allocation's equity weight for a tier."""
    allocation = compute_target_allocation(tier)
    return float(allocation.target_pct[AssetClass.EQUITY] / 100)


def evaluate_fragility(
    profile: dict[str, Any],
    equity_share: float,
    equity_drawdown: float,
    income_loss_months: int,
) -> dict[str, float | bool]:
    """Evaluate the specified cash-flow coverage test without capacity rules.

    The assumed full income interruption leaves no income available during
    the shock months. Liquid cash and the non-equity part of investable
    assets are available for essential expenses and EMI; equity holdings are
    excluded from emergency liquidity. The equity shock is still applied and
    its rupee loss is reported separately.
    """
    if not 0 <= equity_share <= 1:
        raise ValueError("equity_share must be between zero and one")
    if not 0 <= equity_drawdown <= 1:
        raise ValueError("equity_drawdown must be between zero and one")
    if income_loss_months <= 0:
        raise ValueError("income_loss_months must be positive")

    equity_assets = float(profile["investable_assets"]) * equity_share
    equity_loss = equity_assets * equity_drawdown
    available_liquidity = float(profile["liquid_cash"]) + (
        float(profile["investable_assets"]) * (1 - equity_share)
    )
    required_outflows = income_loss_months * (
        float(profile["essential_monthly_expense"]) + float(profile["total_monthly_emi"])
    )
    shortfall = max(0.0, required_outflows - available_liquidity)
    return {
        "violation": shortfall > 0,
        "shortfall_rupees": shortfall,
        "equity_loss_rupees": equity_loss,
    }


def bootstrap_mean_cis(
    series: dict[str, np.ndarray],
    seed: int,
    n_resamples: int = int(EXPERIMENT_CONFIG["bootstrap_resamples"]),
) -> dict[str, tuple[float, float]]:
    """Return percentile bootstrap CIs for means, resampling profiles."""
    if n_resamples <= 0 or not series:
        raise ValueError("series must be nonempty and n_resamples must be positive")
    lengths = {len(values) for values in series.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError("all bootstrap series must have the same positive length")

    sample_size = next(iter(lengths))
    rng = np.random.default_rng(seed)
    bootstrap_means = {name: np.empty(n_resamples, dtype=float) for name in series}
    batch_size = int(EXPERIMENT_CONFIG["bootstrap_batch_size"])
    for start in range(0, n_resamples, batch_size):
        stop = min(start + batch_size, n_resamples)
        sample_indices = rng.integers(0, sample_size, size=(stop - start, sample_size))
        for name, values in series.items():
            bootstrap_means[name][start:stop] = values[sample_indices].mean(axis=1)

    tail = (1 - float(EXPERIMENT_CONFIG["confidence_level"])) / 2
    return {
        name: (
            float(np.quantile(means, tail)),
            float(np.quantile(means, 1 - tail)),
        )
        for name, means in bootstrap_means.items()
    }


def _scenario_arrays(
    profiles: list[dict[str, Any]],
    equity_drawdown: float,
    income_loss_months: int,
) -> dict[str, dict[str, np.ndarray]]:
    baseline_equity_shares = np.asarray(
        [equity_share_for_tier(compute_method_tiers(profile)["willingness_only"]) for profile in profiles],
        dtype=float,
    )
    data: dict[str, dict[str, list[float]]] = {
        method: {
            "violation": [],
            "shortfall_rupees": [],
            "equity_share": [],
            "tier_changed": [],
            "equity_share_cost": [],
            "equity_loss_rupees": [],
        }
        for method in METHODS
    }

    for index, profile in enumerate(profiles):
        tiers = compute_method_tiers(profile)
        for method in METHODS:
            tier = tiers[method]
            equity_share = equity_share_for_tier(tier)
            outcome = evaluate_fragility(profile, equity_share, equity_drawdown, income_loss_months)
            data[method]["violation"].append(float(outcome["violation"]))
            data[method]["shortfall_rupees"].append(float(outcome["shortfall_rupees"]))
            data[method]["equity_share"].append(equity_share)
            data[method]["tier_changed"].append(float(tier != tiers["willingness_only"]))
            data[method]["equity_share_cost"].append(baseline_equity_shares[index] - equity_share)
            data[method]["equity_loss_rupees"].append(float(outcome["equity_loss_rupees"]))

    return {
        method: {key: np.asarray(values, dtype=float) for key, values in series.items()}
        for method, series in data.items()
    }


def _metrics_row(
    method: str,
    stratum: str,
    equity_drawdown: float,
    income_loss_months: int,
    values: dict[str, np.ndarray],
    seed: int,
) -> dict[str, Any]:
    metrics = {
        "violation_rate": values["violation"],
        "mean_shortfall_rupees": values["shortfall_rupees"],
        "share_tier_changed_vs_willingness": values["tier_changed"],
        "expected_equity_share": values["equity_share"],
        "equity_share_cost_vs_willingness": values["equity_share_cost"],
        "mean_equity_loss_rupees": values["equity_loss_rupees"],
    }
    confidence_intervals = bootstrap_mean_cis(metrics, seed)
    row: dict[str, Any] = {
        "method": method,
        "method_label": METHOD_LABELS[method],
        "stratum": stratum,
        "equity_drawdown": equity_drawdown,
        "income_loss_months": income_loss_months,
        "n_profiles": len(values["violation"]),
    }
    for name, samples in metrics.items():
        row[name] = float(samples.mean())
        row[f"{name}_ci95_low"] = confidence_intervals[name][0]
        row[f"{name}_ci95_high"] = confidence_intervals[name][1]
    return row


def _format_percent(value: float) -> str:
    return f"{100 * value:.2f}%"


def _format_ci_percent(row: dict[str, Any], metric: str) -> str:
    return (
        f"{_format_percent(float(row[metric]))} "
        f"[{_format_percent(float(row[f'{metric}_ci95_low']))}, "
        f"{_format_percent(float(row[f'{metric}_ci95_high']))}]"
    )


def _format_ci_rupees(row: dict[str, Any], metric: str) -> str:
    return (
        f"₹{float(row[metric]):,.0f} "
        f"[₹{float(row[f'{metric}_ci95_low']):,.0f}, "
        f"₹{float(row[f'{metric}_ci95_high']):,.0f}]"
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    if not rows:
        raise ValueError(f"refusing to write an empty results table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot_main_results(summary: list[dict[str, Any]], output_dir: Path) -> None:
    positions = np.arange(len(summary))
    rates = np.asarray([row["violation_rate"] for row in summary])
    lower = rates - np.asarray([row["violation_rate_ci95_low"] for row in summary])
    upper = np.asarray([row["violation_rate_ci95_high"] for row in summary]) - rates

    fig, axis = plt.subplots(figsize=(11, 6))
    axis.bar(positions, rates, color="#4472C4")
    axis.errorbar(positions, rates, yerr=np.vstack((lower, upper)), fmt="none", ecolor="black", capsize=4)
    axis.set_xticks(positions, [row["method_label"] for row in summary], rotation=25, ha="right")
    axis.set_ylabel("Fragility violation rate")
    axis.set_ylim(0, min(1.0, max(0.05, float((rates + upper).max() * 1.15))))
    axis.set_title("Fragility violation rate by method (95% bootstrap CI)")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "violation_rate_by_method.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9, 6))
    for row in summary:
        axis.scatter(row["expected_equity_share"], row["violation_rate"], s=65)
        axis.annotate(
            row["method_label"],
            (row["expected_equity_share"], row["violation_rate"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )
    axis.set_xlabel("Expected equity allocation share")
    axis.set_ylabel("Fragility violation rate")
    axis.set_title("Liquidity fragility versus expected equity allocation")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "violation_vs_equity_share.png", dpi=160)
    plt.close(fig)


def _write_results_markdown(
    profiles: list[dict[str, Any]],
    main_rows: list[dict[str, Any]],
    strata_rows: list[dict[str, Any]],
    sensitivity_rows: list[dict[str, Any]],
    mcnemar_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    counts = Counter(str(profile["stratum"]) for profile in profiles)
    main = EXPERIMENT_CONFIG["main_scenario"]
    versions = {
        "Python": platform.python_version(),
        "NumPy": np.__version__,
        "SciPy": scipy.__version__,
        "Matplotlib": matplotlib.__version__,
        "V2 questionnaire": QUESTIONNAIRE_V2.version,
        "Capacity rule table": CAPACITY_RULE_TABLE_V1.version,
        "Allocation configuration": CONFIG_VERSION,
    }

    lines = [
        "# Capacity-first fragility experiment",
        "",
        "## Design and reproducibility",
        "",
        f"- Synthetic profiles: {len(profiles)}.",
        f"- Cohort seed: {COHORT_CONFIG['seed']}; bootstrap seed: {EXPERIMENT_CONFIG['bootstrap_seed']}.",
        f"- Main scenario: equity drawdown {_format_percent(main['equity_drawdown'])}; full income loss for {main['income_loss_months']} months.",
        f"- Bootstrap: {EXPERIMENT_CONFIG['bootstrap_resamples']} profile-resamples; "
        f"{100 * EXPERIMENT_CONFIG['confidence_level']:.0f}% percentile intervals.",
        "- Production scoring/capacity methods: `compute_stated_tier`, `compute_capacity_ceiling`, and `compute_final_tier`.",
        "- Tier allocations and equity percentages come from production `compute_target_allocation`.",
        "",
        "### Cohort distribution documentation",
        "",
        COHORT_DISTRIBUTION_DOCUMENTATION or "",
        "",
        "```json",
        json.dumps(COHORT_CONFIG, indent=2, default=str),
        "```",
        "",
        "### Generated stratum counts",
        "",
        "| Stratum | Profiles | Share |",
        "|---|---:|---:|",
    ]
    for stratum in STRATUM_ORDER:
        lines.append(
            f"| {stratum.replace('_', ' ')} | {counts[stratum]} | "
            f"{_format_percent(counts[stratum] / len(profiles))} |"
        )

    lines.extend(
        [
            "",
            "## Main-scenario results",
            "",
            "The violation rate, mean shortfall (zero included for profiles without a violation), "
            "tier-change share, expected equity share, and equity-share cost are cohort means. "
            "Bracketed intervals are 95% profile-bootstrap confidence intervals. Equity-share cost "
            "is willingness-only equity share minus method equity share; positive values are equity "
            "allocation given up.",
            "",
            "| Method | Violation rate (95% CI) | Mean shortfall (95% CI) | Tier changed vs willingness (95% CI) | Expected equity share (95% CI) | Equity-share cost (95% CI) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in main_rows:
        lines.append(
            f"| {row['method_label']} | {_format_ci_percent(row, 'violation_rate')} "
            f"| {_format_ci_rupees(row, 'mean_shortfall_rupees')} "
            f"| {_format_ci_percent(row, 'share_tier_changed_vs_willingness')} "
            f"| {_format_ci_percent(row, 'expected_equity_share')} "
            f"| {_format_ci_percent(row, 'equity_share_cost_vs_willingness')} |"
        )

    lines.extend(
        [
            "",
            "### Paired McNemar tests",
            "",
            "Two-sided exact binomial tests on discordant paired violation outcomes.",
            "",
            "| Comparison | D violates, comparator does not | D does not, comparator violates | Discordant pairs | Exact p-value |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in mcnemar_rows:
        lines.append(
            f"| Gated minimum vs {METHOD_LABELS[row['comparator']]} | "
            f"{row['gated_violates_only']} | {row['comparator_violates_only']} | "
            f"{row['discordant_pairs']} | {row['p_value']:.6g} |"
        )

    lines.extend(
        [
            "",
            "## Results by stratum",
            "",
            "| Stratum | Method | Violation rate (95% CI) | Mean shortfall (95% CI) | Tier changed (95% CI) | Expected equity share (95% CI) | Equity-share cost (95% CI) |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in strata_rows:
        lines.append(
            f"| {row['stratum'].replace('_', ' ')} | {row['method_label']} "
            f"| {_format_ci_percent(row, 'violation_rate')} "
            f"| {_format_ci_rupees(row, 'mean_shortfall_rupees')} "
            f"| {_format_ci_percent(row, 'share_tier_changed_vs_willingness')} "
            f"| {_format_ci_percent(row, 'expected_equity_share')} "
            f"| {_format_ci_percent(row, 'equity_share_cost_vs_willingness')} |"
        )

    lines.extend(
        [
            "",
            "## Sensitivity grid",
            "",
            "| Equity drawdown | Income-loss months | Method | Violation rate (95% CI) | Mean shortfall (95% CI) | Mean equity loss (95% CI) |",
            "|---:|---:|---|---:|---:|---:|",
        ]
    )
    for row in sensitivity_rows:
        lines.append(
            f"| {_format_percent(row['equity_drawdown'])} | {row['income_loss_months']} "
            f"| {row['method_label']} | {_format_ci_percent(row, 'violation_rate')} "
            f"| {_format_ci_rupees(row, 'mean_shortfall_rupees')} "
            f"| {_format_ci_rupees(row, 'mean_equity_loss_rupees')} |"
        )

    lines.extend(
        [
            "",
            "## Assumptions",
            "",
            "- Every profile suffers a complete interruption of monthly income during all specified loss months; no replacement income or public/private benefits are modeled.",
            "- Stress-period outflows are essential monthly expenses plus EMI. Other monthly expenses are generated and saved but excluded from the specified fragility predicate.",
            "- Liquid cash and all non-equity investable assets are treated as immediately available at face value; equity is excluded from emergency liquidity.",
            "- Equity drawdown applies to the equity share of investable assets and is reported as an equity loss. Since equity is excluded from emergency liquidity, changing the drawdown percentage does not itself change the coverage predicate; tiers and non-equity shares still affect available liquidity.",
            "- Investable assets and liquid cash are separate balances; no double counting or additional liabilities beyond the supplied EMI are modeled.",
            "- Profiles are synthetic, deliberately stratified, and not sampled from or calibrated to a representative population.",
            "- The 50/50 blend uses Python's built-in `round` behavior for half-integer values.",
            "- The no-insurance ablation sets dependents to zero only for capacity calculation; the no-EMI ablation sets EMI ratio/outflow to zero only for capacity calculation. Each ablation retains the original profile in the shock outcome.",
            "- Bootstrap intervals resample profiles and quantify sampling variation within this synthetic cohort, not uncertainty about real-world distributions or model assumptions.",
            "",
            "## Threats to validity",
            "",
            "- The engineered disagreement strata guarantee adequate representation but distort their natural prevalence and may exaggerate method differences.",
            "- Income, expense, wealth, dependents, insurance, and questionnaire responses use simplified distributions and dependencies; they do not capture household heterogeneity, debt types, taxes, inflation, or geography.",
            "- Treating all non-equity investments as liquid at face value can overstate emergency resources; excluding all equity can be conservative for holdings that are readily saleable.",
            "- The complete income-loss assumption and fixed outflow treatment do not represent partial income shocks, consumption adjustment, or post-shock recovery.",
            "- The result is sensitive to the production questionnaire, tier cutoffs, capacity policy, and allocation assumptions; none is an independently validated measure of a household's true risk tolerance or resilience.",
            "- Shortfalls are deterministic scenario outcomes, not forecasts of realized losses or evidence of causal effects.",
            "",
            "## Software and project versions",
            "",
            "| Component | Version |",
            "|---|---|",
        ]
    )
    for component, version in versions.items():
        lines.append(f"| {component} | {version} |")

    lines.extend(
        [
            "",
            "## Generated files",
            "",
            "- `cohort.csv` — synthetic profiles and their verified strata.",
            "- `main_summary.csv` — overall main-scenario outcomes and intervals.",
            "- `strata_summary.csv` — main-scenario outcomes by stratum.",
            "- `sensitivity_summary.csv` — outcomes across the drawdown/loss-duration grid.",
            "- `mcnemar_tests.csv` — paired tests for gated minimum versus willingness-only and blend.",
            "- `experiment_summary.json` — configuration, versions, cohort counts, and all tabular results.",
            "- `violation_rate_by_method.png` and `violation_vs_equity_share.png` — main-scenario figures.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_experiment() -> dict[str, Path]:
    """Generate the cohort, tables, figures, and report in the results folder."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    profiles = generate_cohort()
    save_cohort(profiles)
    group_indices = {
        stratum: np.asarray(
            [index for index, profile in enumerate(profiles) if profile["stratum"] == stratum],
            dtype=int,
        )
        for stratum in STRATUM_ORDER
    }
    main = EXPERIMENT_CONFIG["main_scenario"]
    scenario_cache: dict[tuple[float, int], dict[str, dict[str, np.ndarray]]] = {}
    summary_rows: list[dict[str, Any]] = []
    strata_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    seed_offset = 0

    scenarios = [
        (float(drawdown), int(months))
        for drawdown in EXPERIMENT_CONFIG["sensitivity_equity_drawdowns"]
        for months in EXPERIMENT_CONFIG["sensitivity_income_loss_months"]
    ]
    if (float(main["equity_drawdown"]), int(main["income_loss_months"])) not in scenarios:
        scenarios.append((float(main["equity_drawdown"]), int(main["income_loss_months"])))

    for equity_drawdown, income_loss_months in scenarios:
        values_by_method = _scenario_arrays(profiles, equity_drawdown, income_loss_months)
        scenario_cache[(equity_drawdown, income_loss_months)] = values_by_method
        is_main = (
            equity_drawdown == float(main["equity_drawdown"])
            and income_loss_months == int(main["income_loss_months"])
        )
        for method in METHODS:
            values = values_by_method[method]
            full_row = _metrics_row(
                method,
                "all",
                equity_drawdown,
                income_loss_months,
                values,
                int(EXPERIMENT_CONFIG["bootstrap_seed"]) + seed_offset,
            )
            seed_offset += 1
            sensitivity_rows.append(
                {
                    key: full_row[key]
                    for key in (
                        "method",
                        "method_label",
                        "equity_drawdown",
                        "income_loss_months",
                        "n_profiles",
                        "violation_rate",
                        "violation_rate_ci95_low",
                        "violation_rate_ci95_high",
                        "mean_shortfall_rupees",
                        "mean_shortfall_rupees_ci95_low",
                        "mean_shortfall_rupees_ci95_high",
                        "mean_equity_loss_rupees",
                        "mean_equity_loss_rupees_ci95_low",
                        "mean_equity_loss_rupees_ci95_high",
                    )
                }
            )
            if is_main:
                summary_rows.append(full_row)
                for stratum in STRATUM_ORDER:
                    indices = group_indices[stratum]
                    subset = {key: samples[indices] for key, samples in values.items()}
                    stratum_row = _metrics_row(
                        method,
                        stratum,
                        equity_drawdown,
                        income_loss_months,
                        subset,
                        int(EXPERIMENT_CONFIG["bootstrap_seed"]) + seed_offset,
                    )
                    seed_offset += 1
                    strata_rows.append(
                        {
                            key: stratum_row[key]
                            for key in (
                                "method",
                                "method_label",
                                "stratum",
                                "n_profiles",
                                "violation_rate",
                                "violation_rate_ci95_low",
                                "violation_rate_ci95_high",
                                "mean_shortfall_rupees",
                                "mean_shortfall_rupees_ci95_low",
                                "mean_shortfall_rupees_ci95_high",
                                "share_tier_changed_vs_willingness",
                                "share_tier_changed_vs_willingness_ci95_low",
                                "share_tier_changed_vs_willingness_ci95_high",
                                "expected_equity_share",
                                "expected_equity_share_ci95_low",
                                "expected_equity_share_ci95_high",
                                "equity_share_cost_vs_willingness",
                                "equity_share_cost_vs_willingness_ci95_low",
                                "equity_share_cost_vs_willingness_ci95_high",
                            )
                        }
                    )

    main_values = scenario_cache[(float(main["equity_drawdown"]), int(main["income_loss_months"]))]
    mcnemar_rows: list[dict[str, Any]] = []
    for comparator in ("willingness_only", "blend"):
        gated_violations = main_values["gated_min"]["violation"].astype(bool)
        comparator_violations = main_values[comparator]["violation"].astype(bool)
        gated_only = int(np.sum(gated_violations & ~comparator_violations))
        comparator_only = int(np.sum(~gated_violations & comparator_violations))
        discordant = gated_only + comparator_only
        p_value = (
            float(binomtest(gated_only, discordant, p=0.5, alternative="two-sided").pvalue)
            if discordant
            else 1.0
        )
        mcnemar_rows.append(
            {
                "gated_method": "gated_min",
                "comparator": comparator,
                "gated_violates_only": gated_only,
                "comparator_violates_only": comparator_only,
                "discordant_pairs": discordant,
                "p_value": p_value,
            }
        )

    paths = {
        "cohort": RESULTS_DIR / "cohort.csv",
        "main_summary": RESULTS_DIR / "main_summary.csv",
        "strata_summary": RESULTS_DIR / "strata_summary.csv",
        "sensitivity_summary": RESULTS_DIR / "sensitivity_summary.csv",
        "mcnemar_tests": RESULTS_DIR / "mcnemar_tests.csv",
        "json_summary": RESULTS_DIR / "experiment_summary.json",
        "violation_plot": RESULTS_DIR / "violation_rate_by_method.png",
        "tradeoff_plot": RESULTS_DIR / "violation_vs_equity_share.png",
        "report": RESULTS_DIR / "results.md",
    }
    _write_csv(paths["main_summary"], summary_rows)
    _write_csv(paths["strata_summary"], strata_rows)
    _write_csv(paths["sensitivity_summary"], sensitivity_rows)
    _write_csv(paths["mcnemar_tests"], mcnemar_rows)
    _plot_main_results(summary_rows, RESULTS_DIR)
    software_versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "matplotlib": matplotlib.__version__,
        "questionnaire": QUESTIONNAIRE_V2.version,
        "capacity_rule_table": CAPACITY_RULE_TABLE_V1.version,
        "allocation_configuration": CONFIG_VERSION,
    }
    paths["json_summary"].write_text(
        json.dumps(
            {
                "cohort_config": COHORT_CONFIG,
                "experiment_config": EXPERIMENT_CONFIG,
                "software_versions": software_versions,
                "cohort_size": len(profiles),
                "stratum_counts": dict(Counter(str(profile["stratum"]) for profile in profiles)),
                "main_summary": summary_rows,
                "strata_summary": strata_rows,
                "sensitivity_summary": sensitivity_rows,
                "mcnemar_tests": mcnemar_rows,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    _write_results_markdown(
        profiles,
        summary_rows,
        strata_rows,
        sensitivity_rows,
        mcnemar_rows,
        paths["report"],
    )
    return paths


if __name__ == "__main__":
    generated = run_experiment()
    for name, path in generated.items():
        print(f"{name}: {path}")
