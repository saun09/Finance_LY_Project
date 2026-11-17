"""Reproducible synthetic cohort construction for the capacity-first study.

Distribution and construction rationale (exact parameters are in
``COHORT_CONFIG`` and are serialized into results.md):

* The configured 30/30/40 percent quota is deliberately stratified, rather
  than population-representative, to guarantee both disagreement directions
  and a comparison group. Largest-remainder allocation keeps requested sizes
  reproducible for arbitrary cohort sizes.
* Monthly income is lognormal within each stratum (stratum-specific medians
  and log-scale sigmas) because earnings/wealth-like values are positive and
  right-skewed. Investable assets are monthly income multiplied by an
  independent lognormal multiplier; this gives a right tail and allows
  households with similar income to hold different non-cash wealth.
* Essential and other monthly expenses are separate beta-distributed
  fractions of income. Their positive income correlation is more plausible
  than independently sampled rupee amounts, and beta support keeps fractions
  bounded. Stratum-specific shapes create intentionally different expense
  burdens without changing the outcome formula.
* Liquid cash is a uniform number of essential-expense months; EMI is a
  uniform share of income. These conditional distributions make buffer and
  debt obligations interpretable and let the constructed strata meet their
  assigned capacity patterns.
* Dependents follow a Poisson count; aligned and single-barrier profiles
  have at least one dependent so their insurance dimension is meaningful.
  Life cover is a uniform fraction of the configured required-cover base,
  yielding under-covered, adequate, or deliberately constrained examples.
* Income stability is assigned categorically by stratum/barrier to control
  a capacity dimension directly; single-barrier cases use regular income so
  their designated insurance or EMI constraint can be isolated.
* The seven V2 questionnaire answers are sampled from option ranks 4/5 for
  willing-but-unable, 1/2 for able-but-unwilling, and rank 3 for aligned
  profiles. The high/low rank probabilities add within-stratum variation;
  midpoint answers make aligned profiles land on the questionnaire's
  middle tier.
* The exact 30/30/40 strata intentionally construct both directional
  disagreements: willing-but-unable profiles have high questionnaire scores
  and mixed binding barriers (buffer/stability, insurance alone, or EMI
  alone); able-but-unwilling profiles have low scores and strong capacity;
  aligned profiles have midpoint answers and a matching middle capacity
  tier. The generated stratum is validated against production scoring and
  capacity functions.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np

from app.services.risk_profile import IncomeStabilityValue
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1, QUESTIONNAIRE_V2

from research_artifacts.experiments.common import capacity_inputs_from_profile, score_profile


# All cohort-generation parameters live here; results.md serializes this
# exact block so the synthetic design is inspectable alongside its outputs.
COHORT_CONFIG: dict[str, Any] = {
    "n_profiles": 5000,
    "seed": 42,
    "stratum_shares": {
        "willing_but_unable": 0.30,
        "able_but_unwilling": 0.30,
        "aligned": 0.40,
    },
    "willing_but_unable_barrier_shares": {
        "buffer_stability": 0.50,
        "insurance_only": 0.25,
        "emi_only": 0.25,
    },
    "income_lognormal_median_rupees": {
        "willing_but_unable": 50000,
        "able_but_unwilling": 80000,
        "aligned": 65000,
    },
    "income_lognormal_sigma": {
        "willing_but_unable": 0.55,
        "able_but_unwilling": 0.50,
        "aligned": 0.52,
    },
    "essential_expense_fraction_beta_shapes": {
        "willing_but_unable": (6.0, 4.0),
        "able_but_unwilling": (4.0, 7.0),
        "aligned": (5.0, 7.0),
    },
    "other_expense_fraction_beta_shapes": {
        "willing_but_unable": (3.0, 12.0),
        "able_but_unwilling": (2.5, 14.0),
        "aligned": (2.8, 13.0),
    },
    "cash_buffer_months_uniform": {
        "willing_but_unable": (0.20, 0.90),
        "able_but_unwilling": (6.0, 15.0),
        "aligned": (2.20, 3.80),
    },
    "emi_to_income_uniform": {
        "willing_but_unable": (0.35, 0.65),
        "able_but_unwilling": (0.05, 0.18),
        "aligned": (0.32, 0.38),
    },
    "income_stability": {
        "willing_but_unable": IncomeStabilityValue.IRREGULAR.value,
        "able_but_unwilling": IncomeStabilityValue.REGULAR.value,
        "aligned": IncomeStabilityValue.REGULAR.value,
    },
    "dependents_poisson_lambda": 1.4,
    "life_cover_required_income_multiple": CAPACITY_RULE_TABLE_V1.required_life_cover_income_multiple,
    "life_cover_ratio_uniform": {
        "willing_but_unable": (0.00, 0.20),
        "able_but_unwilling": (1.05, 1.70),
        "aligned": (0.55, 0.70),
    },
    "investable_assets_to_income_lognormal_median": {
        "willing_but_unable": 8.0,
        "able_but_unwilling": 15.0,
        "aligned": 11.0,
    },
    "investable_assets_to_income_lognormal_sigma": 0.65,
    "questionnaire_option_ranks": {
        "willing_but_unable": (4, 5),
        "able_but_unwilling": (1, 2),
        "aligned": (3, 3),
    },
    "high_low_answer_rank_probabilities": (0.65, 0.35),
}

RESULTS_DIR = Path(__file__).resolve().parent / "results"
STRATUM_ORDER = ("willing_but_unable", "able_but_unwilling", "aligned")


def generate_cohort(
    n_profiles: int = int(COHORT_CONFIG["n_profiles"]),
    seed: int = int(COHORT_CONFIG["seed"]),
) -> list[dict[str, Any]]:
    """Generate an exactly reproducible synthetic cohort.

    The configured stratum shares are converted to integer group sizes using
    largest-remainder allocation. Numeric financial values are stored as
    integer rupees; the production capacity inputs use paise conversions.
    """
    if n_profiles <= 0:
        raise ValueError("n_profiles must be positive")

    rng = np.random.default_rng(seed)
    raw_counts = {name: n_profiles * float(COHORT_CONFIG["stratum_shares"][name]) for name in STRATUM_ORDER}
    sizes = {name: int(np.floor(value)) for name, value in raw_counts.items()}
    remainder = n_profiles - sum(sizes.values())
    for name in sorted(STRATUM_ORDER, key=lambda key: raw_counts[key] - sizes[key], reverse=True)[:remainder]:
        sizes[name] += 1

    group_names = np.concatenate(
        [np.repeat(name, sizes[name]) for name in STRATUM_ORDER]
    )
    rng.shuffle(group_names)
    option_ranks = {
        question.id: {rank: option.value for rank, option in enumerate(question.options, start=1)}
        for question in QUESTIONNAIRE_V2.questions
    }

    rows: list[dict[str, Any]] = []
    for profile_index, stratum in enumerate(group_names):
        stratum = str(stratum)
        barrier = (
            str(
                rng.choice(
                    tuple(COHORT_CONFIG["willing_but_unable_barrier_shares"]),
                    p=tuple(COHORT_CONFIG["willing_but_unable_barrier_shares"].values()),
                )
            )
            if stratum == "willing_but_unable"
            else "aligned"
            if stratum == "aligned"
            else "high_capacity"
        )
        has_single_barrier = barrier in {"insurance_only", "emi_only"}
        cash_and_other_capacity_group = "able_but_unwilling" if has_single_barrier else stratum
        income_median = float(COHORT_CONFIG["income_lognormal_median_rupees"][stratum])
        income_sigma = float(COHORT_CONFIG["income_lognormal_sigma"][stratum])
        income = max(1, int(np.rint(rng.lognormal(np.log(income_median), income_sigma))))

        essential_alpha, essential_beta = COHORT_CONFIG["essential_expense_fraction_beta_shapes"][stratum]
        essential_fraction = float(rng.beta(essential_alpha, essential_beta))
        essential_expense = max(1, int(np.rint(income * essential_fraction)))

        other_alpha, other_beta = COHORT_CONFIG["other_expense_fraction_beta_shapes"][stratum]
        other_fraction = float(rng.beta(other_alpha, other_beta))
        other_expense = max(0, int(np.rint(income * other_fraction)))

        buffer_low, buffer_high = COHORT_CONFIG["cash_buffer_months_uniform"][cash_and_other_capacity_group]
        cash_months = float(rng.uniform(buffer_low, buffer_high))
        liquid_cash = max(0, int(np.rint(essential_expense * cash_months)))

        emi_group = stratum if barrier == "emi_only" else cash_and_other_capacity_group
        emi_low, emi_high = COHORT_CONFIG["emi_to_income_uniform"][emi_group]
        emi_ratio = float(rng.uniform(emi_low, emi_high))
        monthly_emi = max(0, int(np.rint(income * emi_ratio)))

        dependents = int(rng.poisson(float(COHORT_CONFIG["dependents_poisson_lambda"])))
        if stratum == "aligned" or has_single_barrier:
            dependents = max(1, dependents)

        cover_group = (
            "willing_but_unable"
            if barrier == "insurance_only"
            else "able_but_unwilling"
            if barrier == "emi_only"
            else stratum
        )
        cover_low, cover_high = COHORT_CONFIG["life_cover_ratio_uniform"][cover_group]
        cover_ratio = float(rng.uniform(cover_low, cover_high))
        required_cover = (
            income
            * 12
            * int(COHORT_CONFIG["life_cover_required_income_multiple"])
        )
        total_life_cover = max(0, int(np.rint(required_cover * cover_ratio)))

        assets_multiple_median = float(
            COHORT_CONFIG["investable_assets_to_income_lognormal_median"][stratum]
        )
        assets_multiple = float(
            rng.lognormal(
                np.log(assets_multiple_median),
                float(COHORT_CONFIG["investable_assets_to_income_lognormal_sigma"]),
            )
        )
        investable_assets = max(0, int(np.rint(income * assets_multiple)))

        ranks_low, ranks_high = COHORT_CONFIG["questionnaire_option_ranks"][stratum]
        if ranks_low == ranks_high:
            answer_ranks = [int(ranks_low)] * len(QUESTIONNAIRE_V2.questions)
        else:
            answer_ranks = rng.choice(
                (int(ranks_low), int(ranks_high)),
                size=len(QUESTIONNAIRE_V2.questions),
                p=COHORT_CONFIG["high_low_answer_rank_probabilities"],
            ).tolist()

        row: dict[str, Any] = {
            "profile_id": f"synthetic-{profile_index + 1:05d}",
            "stratum": stratum,
            "capacity_barrier": barrier,
            "monthly_income": income,
            "income_stability": (
                IncomeStabilityValue.REGULAR.value
                if has_single_barrier
                else str(COHORT_CONFIG["income_stability"][stratum])
            ),
            "essential_monthly_expense": essential_expense,
            "other_monthly_expense": other_expense,
            "liquid_cash": liquid_cash,
            "total_monthly_emi": monthly_emi,
            "dependents_count": dependents,
            "total_life_cover": total_life_cover,
            "investable_assets": investable_assets,
        }
        for question, rank in zip(QUESTIONNAIRE_V2.questions, answer_ranks):
            row[question.id] = option_ranks[question.id][int(rank)]

        stated_tier, capacity_ceiling = score_profile(row)
        actual_stratum = (
            "willing_but_unable"
            if stated_tier > capacity_ceiling
            else "able_but_unwilling"
            if capacity_ceiling > stated_tier
            else "aligned"
        )
        if actual_stratum != stratum:
            raise RuntimeError(
                f"constructed {stratum} profile produced {actual_stratum}: "
                f"stated tier {stated_tier}, capacity ceiling {capacity_ceiling}"
            )
        row["stated_tier"] = stated_tier
        row["capacity_ceiling"] = capacity_ceiling
        rows.append(row)

    return rows


def save_cohort(rows: list[dict[str, Any]], output_path: Path | None = None) -> Path:
    """Write cohort rows as a CSV under the experiment results directory."""
    path = output_path or RESULTS_DIR / "cohort.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot save an empty cohort")
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


if __name__ == "__main__":
    cohort_rows = generate_cohort()
    cohort_path = save_cohort(cohort_rows)
    print(f"Saved {len(cohort_rows)} profiles to {cohort_path}")
