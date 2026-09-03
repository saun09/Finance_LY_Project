from decimal import Decimal

import pytest

from app.models.onboarding import EmploymentType, IncomeStability, InsuranceType
from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import AssetClass, HoldingType
from app.services.onboarding import add_holding, upsert_profile
from app.services.personalization import EditActionTaken
from app.services.personalization_service import (
    AllocationEventNotFoundError,
    NoAllocationSuggestionError,
    NoRiskTierError,
    compute_and_log_personalization,
    record_allocation_outcome,
)
from app.services.risk_profile_service import compute_and_log_risk_tier

USER = "personalization-user-1"

CONSERVATIVE_ANSWERS = {
    "horizon": "lt_1y",
    "drawdown_reaction": "sell_all",
    "experience": "none",
    "goal": "preserve",
}


def _onboard_strong_capacity_conservative_stated(session):
    # regular income, huge buffer, no EMIs, no dependents -> capacity
    # ceiling 5; stated answers are conservative -> final tier 1. This
    # gives plenty of headroom between final tier's equity target (10%)
    # and the capacity ceiling's equity target (65%) to see the offset
    # actually move the displayed number.
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=10_000_000_00,
    )
    add_holding(session, user_id=USER, description="Equity fund", value_paise=100_000_00, holding_type=HoldingType.EQUITY_MUTUAL_FUND)
    compute_and_log_risk_tier(session, USER, CONSERVATIVE_ANSWERS)
    compute_and_log_allocation(session, USER)


def test_no_allocation_suggestion_raises(session):
    with pytest.raises(NoAllocationSuggestionError):
        compute_and_log_personalization(session, USER)


def test_no_risk_tier_raises(session):
    # Module 4 itself requires a risk tier before it will log an
    # allocation event, so this ordering gap can't happen through the
    # normal flow -- exercised here as a defensive check in this
    # function's own preconditions, by inserting an allocation-shaped
    # event directly without ever computing a risk tier first.
    from app.services.event_log import log_suggestion_event

    log_suggestion_event(
        session,
        user_id=USER,
        module_source="allocation",
        suggested_value={"target_pct": {"cash": "15", "debt": "40", "equity": "35", "real_assets": "8", "alternatives": "2"}, "final_tier": 3},
    )
    with pytest.raises(NoRiskTierError):
        compute_and_log_personalization(session, USER)


def test_no_edits_yet_gives_zero_offset_and_unchanged_display(session):
    _onboard_strong_capacity_conservative_stated(session)

    result = compute_and_log_personalization(session, USER)

    assert result.offset_pct_points == Decimal("0")
    assert result.edits_considered == 0
    assert result.final_tier == 1
    assert result.capacity_ceiling == 5
    assert result.base_target_pct[AssetClass.EQUITY] == Decimal("10")
    assert result.displayed_target_pct[AssetClass.EQUITY] == Decimal("10.00")


def test_recorded_funded_edit_moves_the_displayed_allocation(session):
    _onboard_strong_capacity_conservative_stated(session)

    allocation_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="allocation").one()
    record_allocation_outcome(
        session,
        USER,
        allocation_event.event_id,
        action_taken=EditActionTaken.EDITED,
        chosen_target_pct={"cash": "5", "debt": "50", "equity": "25", "real_assets": "15", "alternatives": "5"},
        funded=True,
    )

    result = compute_and_log_personalization(session, USER)

    # delta = 25 - 10 = 15, alpha=0.3, weight=1 -> offset = 0.3*15 = 4.5
    assert result.offset_pct_points == Decimal("4.500")
    assert result.edits_considered == 1
    assert result.displayed_target_pct[AssetClass.EQUITY] == Decimal("14.50")  # 10 + 4.5
    assert sum(result.displayed_target_pct.values()) == Decimal("100.00")


def test_rejection_leaves_offset_at_zero(session):
    _onboard_strong_capacity_conservative_stated(session)
    allocation_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="allocation").one()
    record_allocation_outcome(
        session, USER, allocation_event.event_id, action_taken=EditActionTaken.REJECTED, chosen_target_pct=None, funded=None,
    )

    result = compute_and_log_personalization(session, USER)
    assert result.offset_pct_points == Decimal("0")
    assert result.edits_considered == 1  # the rejection IS counted as an edit in the sequence, just zero-weight


def test_risk_tier_and_final_tier_are_never_changed_by_personalization(session):
    _onboard_strong_capacity_conservative_stated(session)
    allocation_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="allocation").one()
    record_allocation_outcome(
        session, USER, allocation_event.event_id, action_taken=EditActionTaken.EDITED,
        chosen_target_pct={"cash": "0", "debt": "0", "equity": "100", "real_assets": "0", "alternatives": "0"}, funded=True,
    )

    result = compute_and_log_personalization(session, USER)
    # even with an extreme edit, the tier fields carried through are
    # untouched -- personalization only ever changes displayed_target_pct
    assert result.final_tier == 1
    assert result.capacity_ceiling == 5


def test_record_allocation_outcome_rejects_wrong_user(session):
    _onboard_strong_capacity_conservative_stated(session)
    allocation_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="allocation").one()

    with pytest.raises(AllocationEventNotFoundError):
        record_allocation_outcome(
            session, "someone-else", allocation_event.event_id, action_taken=EditActionTaken.ACCEPTED, chosen_target_pct=None, funded=False,
        )


def test_record_allocation_outcome_rejects_non_allocation_event(session):
    _onboard_strong_capacity_conservative_stated(session)
    risk_event = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="risk_profile").one()

    with pytest.raises(AllocationEventNotFoundError):
        record_allocation_outcome(
            session, USER, risk_event.event_id, action_taken=EditActionTaken.ACCEPTED, chosen_target_pct=None, funded=False,
        )


def test_logs_a_personalization_suggestion_event(session):
    _onboard_strong_capacity_conservative_stated(session)
    compute_and_log_personalization(session, USER)

    events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="personalization").all()
    assert len(events) == 1
    event = events[0]
    assert event.suggested_value["offset_pct_points"] == "0"
    assert event.suggested_value["capacity_ceiling"] == 5
    assert event.suggested_value["final_tier"] == 1
    assert "trace" in event.market_context
