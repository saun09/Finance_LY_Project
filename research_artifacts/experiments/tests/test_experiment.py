from research_artifacts.experiments.cohort import generate_cohort
from research_artifacts.experiments.common import compute_method_tiers
from research_artifacts.experiments.run_experiment import bootstrap_mean_cis, evaluate_fragility


def test_cohort_generation_is_reproducible_and_has_all_strata():
    first = generate_cohort(n_profiles=100, seed=17)
    second = generate_cohort(n_profiles=100, seed=17)

    assert first == second
    assert {row["stratum"] for row in first} == {
        "willing_but_unable",
        "able_but_unwilling",
        "aligned",
    }
    assert all(len([row[key] for key in (
        "horizon",
        "drawdown_reaction",
        "experience",
        "goal",
        "windfall_allocation",
        "sure_gain_tradeoff",
        "friend_description",
    )]) == 7 for row in first)


def test_production_method_adapters_apply_the_expected_tier_relationships():
    profiles = generate_cohort(n_profiles=600, seed=23)
    insurance_barrier_found = False
    emi_barrier_found = False
    for profile in profiles:
        tiers = compute_method_tiers(profile)
        assert tiers["gated_min"] == min(tiers["willingness_only"], tiers["ability_only"])
        assert 1 <= tiers["blend"] <= 5
        assert 1 <= tiers["gated_min_no_insurance"] <= 5
        assert 1 <= tiers["gated_min_no_emi"] <= 5
        if profile["capacity_barrier"] == "insurance_only":
            insurance_barrier_found = True
            assert tiers["gated_min_no_insurance"] > tiers["gated_min"]
        if profile["capacity_barrier"] == "emi_only":
            emi_barrier_found = True
            assert tiers["gated_min_no_emi"] > tiers["gated_min"]
    assert insurance_barrier_found
    assert emi_barrier_found


def test_fragility_uses_cash_flow_and_reports_equity_loss_separately():
    profile = {
        "investable_assets": 100000,
        "liquid_cash": 10000,
        "essential_monthly_expense": 10000,
        "total_monthly_emi": 2000,
    }

    result = evaluate_fragility(profile, equity_share=0.40, equity_drawdown=0.30, income_loss_months=3)

    assert result["equity_loss_rupees"] == 12000
    assert result["shortfall_rupees"] == 0
    assert result["violation"] is False


def test_fragility_reports_uncovered_obligations():
    profile = {
        "investable_assets": 10000,
        "liquid_cash": 1000,
        "essential_monthly_expense": 10000,
        "total_monthly_emi": 2000,
    }

    result = evaluate_fragility(profile, equity_share=0.50, equity_drawdown=0.40, income_loss_months=3)

    assert result["shortfall_rupees"] == 30000
    assert result["violation"] is True


def test_bootstrap_intervals_are_reproducible_and_bracket_the_mean():
    series = {"x": __import__("numpy").array([0.0, 1.0, 2.0, 3.0])}

    first = bootstrap_mean_cis(series, seed=9, n_resamples=500)
    second = bootstrap_mean_cis(series, seed=9, n_resamples=500)

    assert first == second
    assert first["x"][0] <= series["x"].mean() <= first["x"][1]
