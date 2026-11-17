"""Generate overlapping population-style synthetic risk-profile cohorts.

Parameters are assumptions, not calibrated values. Replace each SOURCE_TO_FILL
marker only after the underlying source and calibration procedure are recorded.
"""

from __future__ import annotations

import csv
import json
import platform
from pathlib import Path
import sys
from typing import Any

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "research_artifacts" / "experiments" / "results_v2"
for import_path in (ROOT, ROOT / "backend"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.services.risk_profile import compute_capacity_ceiling, compute_stated_tier
from app.services.risk_profile_config import (
    CAPACITY_RULE_TABLE_V1,
    QUESTIONNAIRE_V2,
)
from research_artifacts.experiments.common import capacity_inputs_from_profile

# Reproducibility settings and all distribution parameters. Each parameter
# section has its own source field; all values are uncalibrated assumptions.
COHORT_B_CONFIG: dict[str, Any] = {
    "source": "SOURCE_TO_FILL",
    "n_profiles": 10_000,
    "seed": 20261110,
    "income": {
        "source": "SOURCE_TO_FILL",
        # Positive right-skewed monthly income, in rupees.
        "lognormal_median_rupees": 80_000,
        "lognormal_sigma": 0.62,
    },
    "age_proxy": {
        "source": "SOURCE_TO_FILL",
        # A bounded beta variate used only to induce buffer-age dependence.
        "beta_alpha": 2.4,
        "beta_beta": 2.8,
        "minimum_years": 21,
        "range_years": 45,
    },
    "expense_fractions": {
        "source": "SOURCE_TO_FILL",
        # Correlated fractions share a latent normal component; each also
        # moves weakly with standardized log income.
        "essential_intercept": 0.38,
        "essential_income_slope": -0.035,
        "essential_shared_noise_sd": 0.045,
        "essential_individual_noise_sd": 0.055,
        "essential_minimum": 0.12,
        "essential_maximum": 0.72,
        "other_intercept": 0.15,
        "other_income_slope": -0.018,
        "other_shared_noise_sd": 0.025,
        "other_individual_noise_sd": 0.035,
        "other_minimum": 0.01,
        "other_maximum": 0.40,
    },
    "cash_buffer": {
        "source": "SOURCE_TO_FILL",
        # Buffer months rise with income and age proxy, with substantial noise.
        "intercept_months": 3.2,
        "income_z_slope_months": 0.65,
        "age_z_slope_months": 0.75,
        "noise_sd_months": 2.1,
        "minimum_months": 0.05,
        "maximum_months": 24.0,
    },
    "emi": {
        "source": "SOURCE_TO_FILL",
        # A zero-inflated EMI ratio. The continuous positive component spans
        # all four capacity thresholds named in the task.
        "zero_share": 0.22,
        "positive_ratio_minimum": 0.015,
        "positive_ratio_maximum": 0.76,
    },
    "income_stability": {
        "source": "SOURCE_TO_FILL",
        # Regular-income probability is a logistic function of income z-score.
        "baseline_log_odds": 0.30,
        "income_z_log_odds_slope": 0.58,
    },
    "dependents": {
        "source": "SOURCE_TO_FILL",
        # Independent count distribution; dependents are not assigned by group.
        "poisson_lambda": 1.25,
    },
    "life_cover": {
        "source": "SOURCE_TO_FILL",
        # Continuous lognormal multiplier of income x 12 x required multiple.
        "ratio_lognormal_median": 0.72,
        "ratio_lognormal_sigma": 0.85,
    },
    "investable_assets": {
        "source": "SOURCE_TO_FILL",
        # Continuous multiplier of annual income in rupees.
        "income_multiple_lognormal_median": 9.0,
        "income_multiple_lognormal_sigma": 0.82,
    },
    "questionnaire": {
        "source": "SOURCE_TO_FILL",
        # A shared latent propensity plus item-level noise produces ordered
        # answers; the income coefficient is intentionally weak.
        "income_z_coefficient": 0.12,
        "latent_noise_sd": 1.0,
        "item_noise_sd": 0.78,
        "ordered_cutpoints": (-1.0, -0.25, 0.25, 1.0),
    },
    "variants": {
        "source": "SOURCE_TO_FILL",
        # Lower/higher fragility shifts are uncalibrated parameter scenarios.
        "low_fragility": {
            "source": "SOURCE_TO_FILL",
            "buffer_months_shift": 1.0,
            "emi_ratio_shift": -0.08,
            "stability_log_odds_shift": 0.8,
        },
        "baseline": {
            "source": "SOURCE_TO_FILL",
            "buffer_months_shift": 0.0,
            "emi_ratio_shift": 0.0,
            "stability_log_odds_shift": 0.0,
        },
        "high_fragility": {
            "source": "SOURCE_TO_FILL",
            "buffer_months_shift": -1.0,
            "emi_ratio_shift": 0.08,
            "stability_log_odds_shift": -0.8,
        },
    },
}

VARIANT_ORDER = ("low_fragility", "baseline", "high_fragility")
QUESTION_IDS = tuple(question.id for question in QUESTIONNAIRE_V2.questions)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def _draw_base(seed: int, n_profiles: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    income_config = COHORT_B_CONFIG["income"]
    income = rng.lognormal(
        np.log(float(income_config["lognormal_median_rupees"])),
        float(income_config["lognormal_sigma"]),
        n_profiles,
    )
    log_income_z = (
        np.log(income) - np.log(float(income_config["lognormal_median_rupees"]))
    ) / float(income_config["lognormal_sigma"])

    age_config = COHORT_B_CONFIG["age_proxy"]
    age_fraction = rng.beta(
        float(age_config["beta_alpha"]),
        float(age_config["beta_beta"]),
        n_profiles,
    )
    age_proxy = (
        float(age_config["minimum_years"])
        + float(age_config["range_years"]) * age_fraction
    )
    age_std = float(age_fraction.std())
    age_z = (
        (age_fraction - age_fraction.mean()) / age_std
        if age_std > 0
        else np.zeros(n_profiles)
    )

    expense = COHORT_B_CONFIG["expense_fractions"]
    shared = rng.normal(size=n_profiles)
    essential_fraction = np.clip(
        float(expense["essential_intercept"])
        + float(expense["essential_income_slope"]) * log_income_z
        + float(expense["essential_shared_noise_sd"]) * shared
        + rng.normal(0, float(expense["essential_individual_noise_sd"]), n_profiles),
        float(expense["essential_minimum"]),
        float(expense["essential_maximum"]),
    )
    other_fraction = np.clip(
        float(expense["other_intercept"])
        + float(expense["other_income_slope"]) * log_income_z
        + float(expense["other_shared_noise_sd"]) * shared
        + rng.normal(0, float(expense["other_individual_noise_sd"]), n_profiles),
        float(expense["other_minimum"]),
        float(expense["other_maximum"]),
    )

    cash_config = COHORT_B_CONFIG["cash_buffer"]
    buffer_noise = rng.normal(0, float(cash_config["noise_sd_months"]), n_profiles)
    base_buffer_months = (
        float(cash_config["intercept_months"])
        + float(cash_config["income_z_slope_months"]) * log_income_z
        + float(cash_config["age_z_slope_months"]) * age_z
        + buffer_noise
    )

    emi_config = COHORT_B_CONFIG["emi"]
    has_emi = rng.random(n_profiles) >= float(emi_config["zero_share"])
    positive_emi_ratio = rng.uniform(
        float(emi_config["positive_ratio_minimum"]),
        float(emi_config["positive_ratio_maximum"]),
        n_profiles,
    )

    stability_uniform = rng.random(n_profiles)
    dependents_config = COHORT_B_CONFIG["dependents"]
    dependents = rng.poisson(float(dependents_config["poisson_lambda"]), n_profiles)

    cover_config = COHORT_B_CONFIG["life_cover"]
    life_cover_ratio = rng.lognormal(
        np.log(float(cover_config["ratio_lognormal_median"])),
        float(cover_config["ratio_lognormal_sigma"]),
        n_profiles,
    )
    assets_config = COHORT_B_CONFIG["investable_assets"]
    asset_multiple = rng.lognormal(
        np.log(float(assets_config["income_multiple_lognormal_median"])),
        float(assets_config["income_multiple_lognormal_sigma"]),
        n_profiles,
    )

    questionnaire_config = COHORT_B_CONFIG["questionnaire"]
    latent_tolerance = (
        rng.normal(0, float(questionnaire_config["latent_noise_sd"]), n_profiles)
        + float(questionnaire_config["income_z_coefficient"]) * log_income_z
    )
    item_noises = rng.normal(
        0,
        float(questionnaire_config["item_noise_sd"]),
        (n_profiles, len(QUESTION_IDS)),
    )
    answer_ranks = np.digitize(
        latent_tolerance[:, None] + item_noises,
        np.asarray(questionnaire_config["ordered_cutpoints"], dtype=float),
    ) + 1
    return {
        "income": income,
        "income_z": log_income_z,
        "age_proxy": age_proxy,
        "essential_fraction": essential_fraction,
        "other_fraction": other_fraction,
        "base_buffer_months": base_buffer_months,
        "has_emi": has_emi,
        "positive_emi_ratio": positive_emi_ratio,
        "stability_uniform": stability_uniform,
        "dependents": dependents,
        "life_cover_ratio": life_cover_ratio,
        "asset_multiple": asset_multiple,
        "latent_tolerance": latent_tolerance,
        "answer_ranks": answer_ranks,
    }


def _score_and_label(row: dict[str, Any], profile_index: int, variant: str) -> None:
    answers = {question_id: str(row[question_id]) for question_id in QUESTION_IDS}
    stated_tier = compute_stated_tier(answers, QUESTIONNAIRE_V2).tier
    capacity = compute_capacity_ceiling(capacity_inputs_from_profile(row))
    ceiling = capacity.ceiling
    posthoc_group = (
        "willing_but_unable"
        if stated_tier > ceiling
        else "able_but_unwilling"
        if ceiling - stated_tier >= 2
        else "aligned"
    )
    row.update(
        {
            "profile_id": f"cohort-b-{variant}-{profile_index + 1:05d}",
            "dataset": variant,
            "stated_tier": stated_tier,
            "capacity_ceiling": ceiling,
            "posthoc_group": posthoc_group,
        }
    )


def generate_variant(
    variant: str,
    *,
    n_profiles: int = int(COHORT_B_CONFIG["n_profiles"]),
    seed: int = int(COHORT_B_CONFIG["seed"]),
) -> list[dict[str, Any]]:
    """Generate one variant using shared random draws and post-hoc labels."""
    if variant not in VARIANT_ORDER:
        raise ValueError(f"unknown fragility variant: {variant}")
    if n_profiles <= 0:
        raise ValueError("n_profiles must be positive")

    base = _draw_base(seed, n_profiles)
    variant_config = COHORT_B_CONFIG["variants"][variant]
    income = base["income"]
    essential_expense = np.maximum(1, np.rint(income * base["essential_fraction"]))
    other_expense = np.maximum(0, np.rint(income * base["other_fraction"]))
    cash_config = COHORT_B_CONFIG["cash_buffer"]
    buffer_months = np.clip(
        base["base_buffer_months"] + float(variant_config["buffer_months_shift"]),
        float(cash_config["minimum_months"]),
        float(cash_config["maximum_months"]),
    )
    emi_config = COHORT_B_CONFIG["emi"]
    emi_ratio = np.where(
        base["has_emi"],
        np.clip(
            base["positive_emi_ratio"] + float(variant_config["emi_ratio_shift"]),
            float(emi_config["positive_ratio_minimum"]),
            0.90,
        ),
        0.0,
    )

    stability_config = COHORT_B_CONFIG["income_stability"]
    regular_probability = _sigmoid(
        float(stability_config["baseline_log_odds"])
        + float(stability_config["income_z_log_odds_slope"]) * base["income_z"]
        + float(variant_config["stability_log_odds_shift"])
    )
    regular = base["stability_uniform"] < regular_probability

    required_cover = (
        income
        * 12
        * float(CAPACITY_RULE_TABLE_V1.required_life_cover_income_multiple)
    )
    answers = {
        question_id: np.asarray(
            [
                next(
                    option.value
                    for option in question.options
                    if rank == option.points
                )
                for rank in base["answer_ranks"][:, question_index]
            ],
            dtype=object,
        )
        for question_index, question_id in enumerate(QUESTION_IDS)
        for question in (next(q for q in QUESTIONNAIRE_V2.questions if q.id == question_id),)
    }

    rows: list[dict[str, Any]] = []
    for index in range(n_profiles):
        row: dict[str, Any] = {
            "monthly_income": int(round(float(income[index]))),
            "age_proxy_years": float(base["age_proxy"][index]),
            "income_stability": "regular" if regular[index] else "irregular",
            "essential_monthly_expense": int(round(float(essential_expense[index]))),
            "other_monthly_expense": int(round(float(other_expense[index]))),
            "liquid_cash": int(
                round(float(essential_expense[index] * buffer_months[index]))
            ),
            "cash_buffer_months": float(buffer_months[index]),
            "total_monthly_emi": int(round(float(income[index] * emi_ratio[index]))),
            "emi_to_income_ratio": float(emi_ratio[index]),
            "dependents_count": int(base["dependents"][index]),
            "life_cover_ratio": float(base["life_cover_ratio"][index]),
            "total_life_cover": int(round(float(required_cover[index] * base["life_cover_ratio"][index]))),
            "investable_assets": int(round(float(income[index] * base["asset_multiple"][index]))),
            "latent_risk_tolerance": float(base["latent_tolerance"][index]),
            **{question_id: str(answers[question_id][index]) for question_id in QUESTION_IDS},
        }
        _score_and_label(row, index, variant)
        rows.append(row)
    return rows


def generate_all_variants(
    *,
    n_profiles: int = int(COHORT_B_CONFIG["n_profiles"]),
    seed: int = int(COHORT_B_CONFIG["seed"]),
) -> dict[str, list[dict[str, Any]]]:
    return {
        variant: generate_variant(variant, n_profiles=n_profiles, seed=seed)
        for variant in VARIANT_ORDER
    }


def save_variant(rows: list[dict[str, Any]], variant: str) -> Path:
    path = RESULTS_DIR / f"cohort_b_{variant}.csv"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing cohort output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot save an empty cohort")
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "questionnaire": QUESTIONNAIRE_V2.version,
        "capacity_rule_table": CAPACITY_RULE_TABLE_V1.version,
    }
    generated = generate_all_variants()
    outputs = {variant: str(save_variant(rows, variant)) for variant, rows in generated.items()}
    print(
        json.dumps(
            {
                "config": COHORT_B_CONFIG,
                "versions": versions,
                "profile_counts": {variant: len(rows) for variant, rows in generated.items()},
                "posthoc_prevalence": {
                    variant: {
                        group: sum(row["posthoc_group"] == group for row in rows) / len(rows)
                        for group in ("willing_but_unable", "able_but_unwilling", "aligned")
                    }
                    for variant, rows in generated.items()
                },
                "outputs": outputs,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
