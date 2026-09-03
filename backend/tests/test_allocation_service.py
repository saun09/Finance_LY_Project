import json

import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.models.suggestion_event import SuggestionEvent
from app.services.asset_classification_config import HoldingType
from app.services.onboarding import add_holding, upsert_profile
from app.services.allocation_service import (
    NoRiskTierError,
    UnclassifiedHoldingsError,
    compute_and_log_allocation,
    gather_holding_classifications,
)
from app.services.risk_profile_service import compute_and_log_risk_tier

USER = "alloc-user-1"

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
}


def _make_profile(session):
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=1_000_000_00,
    )


def test_unclassified_holding_raises_clear_error(session):
    _make_profile(session)
    # a description containing a real-sounding fund name, to make sure the
    # error path (and everything downstream) never has to touch it either
    add_holding(session, user_id=USER, description="Some Mutual Fund I Bought", value_paise=100_000_00)

    with pytest.raises(UnclassifiedHoldingsError):
        gather_holding_classifications(session, USER)


def test_no_risk_tier_raises_clear_error(session):
    _make_profile(session)
    add_holding(
        session, user_id=USER, description="Equity fund", value_paise=100_000_00,
        holding_type=HoldingType.EQUITY_MUTUAL_FUND,
    )
    with pytest.raises(NoRiskTierError):
        compute_and_log_allocation(session, USER)


def _onboard_look_through_portfolio(session):
    _make_profile(session)
    add_holding(
        session, user_id=USER, description="An equity fund", value_paise=100_000_00,
        holding_type=HoldingType.EQUITY_MUTUAL_FUND,
    )
    add_holding(
        session, user_id=USER, description="Savings balance", value_paise=50_000_00,
        holding_type=HoldingType.SAVINGS_ACCOUNT,
    )
    add_holding(
        session, user_id=USER, description="A ULIP policy", value_paise=200_000_00,
        holding_type=HoldingType.ULIP,
    )
    add_holding(
        session, user_id=USER, description="An endowment plan", value_paise=100_000_00,
        holding_type=HoldingType.ENDOWMENT_OR_MONEYBACK_POLICY,
    )
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)


def test_compute_and_log_allocation_shows_look_through_exposure(session):
    _onboard_look_through_portfolio(session)

    report = compute_and_log_allocation(session, USER)

    from app.services.asset_classification_config import AssetClass

    # same hand-checked look-through totals as test_asset_classification.py
    assert report.portfolio.exposure_by_asset_class_paise[AssetClass.EQUITY] == 215_000_00
    assert report.portfolio.exposure_by_asset_class_paise[AssetClass.DEBT] == 185_000_00
    assert report.portfolio.exposure_by_asset_class_paise[AssetClass.CASH] == 50_000_00

    assert report.target.final_tier == 5  # aggressive answers, no capacity constraints set up
    assert sum(report.target.target_pct.values()) == 100


def test_allocation_logs_a_suggestion_event_and_never_leaks_holding_description(session):
    _onboard_look_through_portfolio(session)
    compute_and_log_allocation(session, USER)

    events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="allocation").all()
    assert len(events) == 1
    event = events[0]

    assert event.tier == "5"
    assert event.suggested_value["final_tier"] == 5
    assert event.suggested_value["current_exposure_paise"]["equity"] == 215_000_00
    assert len(event.suggested_value["holdings"]) == 4

    for holding_entry in event.suggested_value["holdings"]:
        assert "description" not in holding_entry
        assert set(holding_entry.keys()) == {
            "holding_id", "holding_type", "value_paise", "decomposition_paise",
            "liquidity", "lock_in_months", "tax_treatment_category", "is_look_through",
        }

    # the hard constraint, checked mechanically: none of the freeform
    # descriptions we entered ("An equity fund", "A ULIP policy", ...)
    # appear anywhere in the serialized logged event
    serialized = json.dumps(event.suggested_value) + json.dumps(event.market_context)
    for description in ("An equity fund", "Savings balance", "A ULIP policy", "An endowment plan"):
        assert description not in serialized


def test_allocation_report_target_matches_pure_lookup_for_the_logged_tier(session):
    _onboard_look_through_portfolio(session)
    report = compute_and_log_allocation(session, USER)

    from app.services.allocation import compute_target_allocation

    expected = compute_target_allocation(report.target.final_tier)
    assert report.target.target_pct == expected.target_pct
