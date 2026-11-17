from research_artifacts.experiments.cohort_b import generate_variant
from research_artifacts.experiments.cohort_b_analysis import (
    ALPHAS,
    METHOD_ORDER,
    SCENARIOS,
    _score,
    _threshold_sensitivity,
    _method_tiers,
    _binding_summary,
    _bootstrap_cis,
    _dataset_evaluation,
    _equity_shares,
    _stress,
)
from research_artifacts.experiments.binding_analysis import (
    _threshold_values,
    perturb_capacity_threshold,
)
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1


def test_population_cohort_is_reproducible_and_posthoc_labeled():
    first = generate_variant("baseline", n_profiles=120, seed=31)
    second = generate_variant("baseline", n_profiles=120, seed=31)

    assert first == second
    assert all("posthoc_group" in row and "stratum" not in row for row in first)
    for row in first:
        stated = row["stated_tier"]
        ceiling = row["capacity_ceiling"]
        expected = (
            "willing_but_unable"
            if stated > ceiling
            else "able_but_unwilling"
            if ceiling - stated >= 2
            else "aligned"
        )
        assert row["posthoc_group"] == expected


def test_population_cohort_crosses_each_emi_band_edge():
    profiles = generate_variant("baseline", n_profiles=5000, seed=62)

    for edge in (0.20, 0.30, 0.40, 0.50):
        assert any(row["emi_to_income_ratio"] < edge for row in profiles)
        assert any(row["emi_to_income_ratio"] > edge for row in profiles)


def test_allocation_methods_include_complete_alpha_sweep():
    profile = generate_variant("baseline", n_profiles=1, seed=42)[0]

    tiers = _method_tiers(profile)

    assert set(ALPHAS) == {round(index / 10, 1) for index in range(11)}
    assert set(tiers) == set(METHOD_ORDER)
    assert all(1 <= tier <= 5 for tier in tiers.values())


def test_binding_summary_counts_unique_and_tied_capped_profiles_once():
    profiles = generate_variant("baseline", n_profiles=200, seed=73)

    summary, _ = _binding_summary(profiles, "baseline")

    assert (
        summary["unique_binding_profiles"] + summary["tied_binding_profiles"]
        == summary["capped_profiles"]
    )


def test_bootstrap_intervals_are_reproducible_and_cover_sample_mean():
    import numpy as np

    values = np.array([[0.0, 10.0], [1.0, 11.0], [2.0, 12.0]])

    first = _bootstrap_cis(values, seed=47)
    second = _bootstrap_cis(values, seed=47)

    assert all(np.array_equal(left, right) for left, right in zip(first, second))
    means = values.mean(axis=0)
    assert all(low <= mean <= high for low, high, mean in zip(*first, means))


def test_optimized_threshold_sensitivity_matches_production_capacity():
    profiles = generate_variant("baseline", n_profiles=40, seed=89)

    rows = _threshold_sensitivity(profiles, "baseline")
    thresholds = _threshold_values(CAPACITY_RULE_TABLE_V1)

    for row in rows:
        field_name, _, threshold = next(
            item for item in thresholds
            if item[0] == row["threshold_field"]
            and item[1] == row["threshold_name"]
            and item[2] == row["base_threshold"]
        )
        table = perturb_capacity_threshold(
            CAPACITY_RULE_TABLE_V1,
            field_name,
            threshold,
            row["perturbation"],
        )
        direct_rate = sum(
            _score(profile, table)[0] > _score(profile, table)[1]
            for profile in profiles
        ) / len(profiles)
        assert row["scenario_cap_rate"] == direct_rate


def test_unavoidable_count_matches_tier_one_floor():
    profiles = generate_variant("baseline", n_profiles=25, seed=97)

    _, _, _, _, extra = _dataset_evaluation(
        profiles,
        "baseline",
        _equity_shares(),
    )
    floor_rows = extra["floor_rows"]

    for row in floor_rows:
        scenario = next(
            scenario for scenario in SCENARIOS
            if scenario["scenario_id"] == row["scenario_id"]
        )
        eligible = [
            profile
            for profile in profiles
            if not scenario["scenario_id"].startswith("S3_")
            or int(profile["dependents_count"]) >= 1
        ]
        floor_count = sum(
            _stress(profile, _equity_shares()[1], scenario)[0]
            for profile in eligible
        )
        assert row["unavoidable_count"] == floor_count


def test_stress_calculations_use_cash_flow_and_drawdown_changes_total_liquid():
    profile = {
        "monthly_income": 100_000,
        "essential_monthly_expense": 20_000,
        "total_monthly_emi": 5_000,
        "liquid_cash": 10_000,
        "investable_assets": 20_000,
        "total_life_cover": 50_000,
        "dependents_count": 1,
    }
    s2 = next(item for item in SCENARIOS if item["scenario_id"] == "S2_total_liquid_3m_20pct")
    s3 = next(item for item in SCENARIOS if item["scenario_id"] == "S3_earner_death_20pct")

    low_drawdown = _stress(profile, 0.5, s2)
    high_drawdown = _stress(profile, 0.5, {**s2, "drawdown": 0.4})
    death = _stress(profile, 0.5, s3)

    assert low_drawdown[1] < high_drawdown[1]
    assert death[2] is True
    assert death[1] >= 0
