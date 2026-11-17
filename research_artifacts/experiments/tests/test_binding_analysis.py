from app.services.risk_profile import CapacityResult, ComponentCeiling
from app.services.risk_profile_config import CAPACITY_RULE_TABLE_V1
from research_artifacts.experiments.binding_analysis import (
    _summarize_cap_rates,
    _tier_matrices,
    binding_component_names,
    build_demo_profiles,
    perturb_capacity_threshold,
)


def test_binding_components_report_unique_and_multiple_ties():
    capacity = CapacityResult(
        rule_table_version="test",
        ceiling=2,
        components=(
            ComponentCeiling("buffer_months", 2, True),
            ComponentCeiling("emi_to_income_ratio", 2, True),
            ComponentCeiling("income_stability", 5, True),
            ComponentCeiling("insurance_adequacy", 1, False),
        ),
    )

    assert binding_component_names(capacity) == ("buffer_months", "emi_to_income_ratio")


def test_threshold_perturbation_copies_table_and_preserves_adjacent_band_edges():
    original = CAPACITY_RULE_TABLE_V1

    changed = perturb_capacity_threshold(
        original,
        field_name="buffer_months_bands",
        threshold=2.0,
        factor=0.10,
    )

    assert changed is not original
    assert original.buffer_months_bands[1].max_value == 2
    assert original.buffer_months_bands[2].min_value == 2
    assert changed.buffer_months_bands[1].max_value == 2.2
    assert changed.buffer_months_bands[2].min_value == 2.2
    assert changed.buffer_months_bands[2].max_value == original.buffer_months_bands[2].max_value


def test_required_life_cover_multiple_perturbation_does_not_mutate_source():
    original = CAPACITY_RULE_TABLE_V1

    changed = perturb_capacity_threshold(
        original,
        field_name="required_life_cover_income_multiple",
        threshold=float(original.required_life_cover_income_multiple),
        factor=-0.10,
    )

    assert changed.required_life_cover_income_multiple == 9
    assert original.required_life_cover_income_multiple == 10


def test_income_stability_ceiling_perturbation_uses_valid_discrete_tiers():
    original = CAPACITY_RULE_TABLE_V1

    lowered = perturb_capacity_threshold(
        original,
        field_name="irregular_income_ceiling",
        threshold=float(original.irregular_income_ceiling),
        factor=-0.10,
    )
    raised = perturb_capacity_threshold(
        original,
        field_name="regular_income_ceiling",
        threshold=float(original.regular_income_ceiling),
        factor=0.10,
    )

    assert lowered.irregular_income_ceiling == 2
    assert raised.regular_income_ceiling == 5
    assert original.irregular_income_ceiling == 3
    assert original.regular_income_ceiling == 5


def test_demo_fixtures_include_all_v2_answers_and_financial_inputs():
    profiles = build_demo_profiles()
    assert len(profiles) == 5
    assert {profile["profile_id"] for profile in profiles} == {
        "seed_dummy_user",
        "seed_showcase_user_initial",
        "seed_showcase_user_after_bonus",
        "seed_feedback_demo_fl_growth",
        "seed_feedback_demo_fl_capped",
    }
    required = {
        "monthly_income",
        "income_stability",
        "essential_monthly_expense",
        "other_monthly_expense",
        "liquid_cash",
        "total_monthly_emi",
        "dependents_count",
        "total_life_cover",
        "horizon",
        "drawdown_reaction",
        "experience",
        "goal",
        "windfall_allocation",
        "sure_gain_tradeoff",
        "friend_description",
    }
    assert all(required <= profile.keys() for profile in profiles)
    assert {profile["profile_id"]: profile["other_monthly_expense"] for profile in profiles}[
        "seed_dummy_user"
    ] == 12500


def test_synthetic_aggregates_do_not_include_demo_fixture_records():
    records = [
        {
            "profile_id": "synthetic-1",
            "stratum": "willing_but_unable",
            "cap_applied": True,
            "stated_tier": 5,
            "final_tier": 2,
        },
        {
            "profile_id": "demo-1",
            "stratum": "demo_data",
            "cap_applied": False,
            "stated_tier": 1,
            "final_tier": 1,
        },
    ]

    rates = _summarize_cap_rates(records)
    counts, _ = _tier_matrices(records)
    overall = next(row for row in rates if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all")
    synthetic_tier_five = next(
        row
        for row in counts
        if row["dataset"] == "synthetic_cohort" and row["stratum"] == "all" and row["stated_tier"] == 5
    )

    assert overall["n_profiles"] == 1
    assert overall["capped_profiles"] == 1
    assert synthetic_tier_five["row_profiles"] == 1
    assert synthetic_tier_five["final_tier_2"] == 1
