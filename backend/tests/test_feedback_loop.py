"""Module 7 end to end: the allocation a user is shown, their response to
that exact event, and the offset the next allocation is built with."""

from decimal import Decimal

import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.models.suggestion_event import ActionTaken, SuggestionEvent
from app.services.allocation import compute_target_allocation
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import AssetClass, HoldingType
from app.services.financial_position import ExpenseFrequency
from app.services.onboarding import add_expense_item, add_holding, upsert_profile
from app.services.personalization import (
    AllocationEdit,
    EditActionTaken,
    compute_offset_from_edits,
)
from app.services.personalization_service import (
    InvalidAllocationOutcomeError,
    compute_and_log_personalization,
    mark_allocation_funded,
    record_allocation_outcome,
)
from app.services.risk_profile_service import compute_and_log_risk_tier
from app.services.transparency import contest_decision, get_trace

USER = "feedback-loop-user"

CONSERVATIVE_ANSWERS = {
    "horizon": "lt_1y",
    "drawdown_reaction": "sell_all",
    "experience": "none",
    "goal": "preserve",
    "windfall_allocation": "fd_or_savings",
    "sure_gain_tradeoff": "guaranteed_5000",
    "friend_description": "real_risk_avoider",
}

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "extensive",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
}

TIER1_EQUITY = compute_target_allocation(1).target_pct[AssetClass.EQUITY]


def _mix(equity: Decimal | str) -> dict[str, str]:
    """A valid five-class mix with the given equity share."""
    equity = Decimal(str(equity))
    rest = Decimal("100") - equity
    return {
        "cash": str(rest * Decimal("0.2")),
        "debt": str(rest * Decimal("0.6")),
        "equity": str(equity),
        "real_assets": str(rest * Decimal("0.2")),
        "alternatives": "0",
    }


def _onboard_room_to_grow(session):
    """Final tier 1 (conservative answers) under a capacity ceiling of 5:
    plenty of equity headroom, so the offset reaches the screen uncapped."""
    upsert_profile(
        session, user_id=USER, income_paise=100_000_00, income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED, dependents_count=0, cash_balance_paise=10_000_000_00,
    )
    add_holding(session, user_id=USER, description="Equity fund", value_paise=100_000_00, holding_type=HoldingType.EQUITY_MUTUAL_FUND)
    compute_and_log_risk_tier(session, USER, CONSERVATIVE_ANSWERS)


def _onboard_capped_by_buffer(session):
    """Aggressive answers, but only 1.5 months of emergency buffer: the
    capacity ceiling (tier 2) is also the final tier, so there is zero
    equity headroom above the base target."""
    upsert_profile(
        session, user_id=USER, income_paise=100_000_00, income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED, dependents_count=0, cash_balance_paise=30_000_00,
    )
    add_expense_item(session, user_id=USER, category="Rent", amount_paise=20_000_00, frequency=ExpenseFrequency.MONTHLY, is_essential=True)
    add_holding(session, user_id=USER, description="Equity fund", value_paise=100_000_00, holding_type=HoldingType.EQUITY_MUTUAL_FUND)
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)


def _allocation_events(session) -> list[SuggestionEvent]:
    return session.query(SuggestionEvent).filter_by(user_id=USER, module_source="allocation").all()


# --- the EWMA itself ---


def test_repeated_funded_edits_converge_toward_the_users_preference():
    edits = [
        AllocationEdit(Decimal("15"), Decimal("21"), EditActionTaken.EDITED, funded=True)
        for _ in range(3)
    ]
    offset, _trace = compute_offset_from_edits(edits)
    # 6 * (1 - 0.7^3): about two thirds of the way to +6 after three edits
    assert offset == Decimal("3.942")


def test_a_confusion_rejection_leaves_a_nonzero_offset_exactly_unchanged():
    edits = [
        AllocationEdit(Decimal("15"), Decimal("25"), EditActionTaken.EDITED, funded=True),
        AllocationEdit(Decimal("15"), None, EditActionTaken.REJECTED, funded=None, reason_code="dont_understand"),
    ]
    offset, trace = compute_offset_from_edits(edits)
    assert offset == Decimal("3.0")
    assert trace[1].weight == 0
    assert trace[1].offset_before == trace[1].offset_after
    assert trace[1].reason_code == "dont_understand"


# --- the loop through the real services ---


def test_reloading_the_allocation_reuses_the_event_until_the_user_responds(session):
    _onboard_room_to_grow(session)

    first = compute_and_log_allocation(session, USER)
    again = compute_and_log_allocation(session, USER)
    assert again.event.event_id == first.event.event_id
    assert len(_allocation_events(session)) == 1

    record_allocation_outcome(
        session, USER, first.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(21), funded=True,
    )
    after = compute_and_log_allocation(session, USER)
    assert after.event.event_id != first.event.event_id
    assert len(_allocation_events(session)) == 2


def test_an_edit_moves_the_next_displayed_mix_and_is_stored_on_the_event_shown(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    assert shown.personalized.displayed_target_pct[AssetClass.EQUITY] == TIER1_EQUITY

    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(TIER1_EQUITY + 6), funded=True,
    )
    session.refresh(shown.event)
    assert shown.event.action_taken == ActionTaken.EDITED
    assert shown.event.delta == {"equity_pct_points": "6.00"}

    nxt = compute_and_log_allocation(session, USER)
    assert nxt.personalized.offset_pct_points == Decimal("1.8")
    assert nxt.personalized.displayed_target_pct[AssetClass.EQUITY] == TIER1_EQUITY + Decimal("1.8")
    assert nxt.event.offset_pct_points == Decimal("1.80")
    assert nxt.event.suggested_value["target_pct"]["equity"] == str(TIER1_EQUITY)  # base never moves


def test_accepting_the_personalized_mix_reinforces_the_offset_instead_of_decaying_it(session):
    _onboard_room_to_grow(session)
    first = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, first.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(TIER1_EQUITY + 6), funded=True,
    )

    second = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, second.event.event_id, action_taken=EditActionTaken.ACCEPTED, chosen_target_pct=None, funded=False,
    )
    session.refresh(second.event)
    # the accept records what was displayed, not a blank
    assert Decimal(second.event.chosen_value["equity"]) == TIER1_EQUITY + Decimal("1.8")

    third = compute_and_log_allocation(session, USER)
    assert third.personalized.offset_pct_points == Decimal("1.8")
    assert [s.weight for s in third.personalized.trace] == [Decimal("1"), Decimal("0.5")]


def test_marking_a_choice_as_invested_later_raises_its_weight(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(TIER1_EQUITY + 10), funded=False,
    )
    assert compute_and_log_allocation(session, USER).personalized.offset_pct_points == Decimal("1.5")

    mark_allocation_funded(session, USER, shown.event.event_id)

    assert compute_and_log_allocation(session, USER).personalized.offset_pct_points == Decimal("3.0")


def test_the_capacity_cap_binds_is_reported_and_never_changes_the_tier(session):
    _onboard_capped_by_buffer(session)
    shown = compute_and_log_allocation(session, USER)
    assert shown.target.final_tier == 2
    base_equity = shown.target.target_pct[AssetClass.EQUITY]

    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(base_equity + 20), funded=True,
    )
    nxt = compute_and_log_allocation(session, USER)

    assert nxt.personalized.offset_pct_points == Decimal("6.0")  # what the history asks for
    cap = nxt.personalized.cap
    assert cap.capped is True
    assert cap.cap_reason == "capacity_ceiling"
    assert cap.applied_offset_pct_points == Decimal("0.00")
    assert nxt.personalized.displayed_target_pct[AssetClass.EQUITY] == base_equity.quantize(Decimal("0.01"))
    assert nxt.personalized.capacity_binding_constraints == ("buffer_months",)
    assert nxt.target.final_tier == 2
    assert nxt.event.suggested_value["offset_capped"] is True


def test_final_tier_never_changes_across_a_whole_session_of_edits(session):
    _onboard_room_to_grow(session)
    for equity in (40, 45, 50, 55, 100):
        shown = compute_and_log_allocation(session, USER)
        record_allocation_outcome(
            session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(equity), funded=True,
        )
    final = compute_and_log_allocation(session, USER)
    assert final.target.final_tier == 1
    assert final.personalized.final_tier == 1
    assert final.personalized.offset_pct_points == Decimal("10")  # clamped at +10
    risk_events = session.query(SuggestionEvent).filter_by(user_id=USER, module_source="risk_profile").all()
    assert len(risk_events) == 1  # nothing in the loop re-tiered the user


def test_contesting_a_decision_keeps_the_users_recorded_edit(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(TIER1_EQUITY + 6), funded=True,
    )

    trace = contest_decision(session, USER, "allocation", shown.event.event_id, "rule_wrong", note="Rule feels off")

    session.refresh(shown.event)
    assert trace.contested is True
    assert shown.event.action_taken == ActionTaken.EDITED
    assert shown.event.funded is True
    assert Decimal(shown.event.chosen_value["equity"]) == TIER1_EQUITY + 6
    assert shown.event.delta["equity_pct_points"] == "6.00"
    assert shown.event.delta["contest_note"] == "Rule feels off"
    assert compute_and_log_allocation(session, USER).personalized.offset_pct_points == Decimal("1.8")


def test_a_plain_rejection_is_not_shown_as_a_contest(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.REJECTED, chosen_target_pct=None, funded=None,
        reason_code="too_risky",
    )
    trace = get_trace(session, USER, "allocation", event_id=shown.event.event_id)
    assert trace.contested is False


def test_personalization_reads_do_not_log_duplicate_events(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)

    compute_and_log_personalization(session, USER)
    compute_and_log_personalization(session, USER)
    assert session.query(SuggestionEvent).filter_by(user_id=USER, module_source="personalization").count() == 1

    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(30), funded=True,
    )
    compute_and_log_personalization(session, USER)
    assert session.query(SuggestionEvent).filter_by(user_id=USER, module_source="personalization").count() == 2


def test_transparency_explains_each_choice_in_plain_words(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, shown.event.event_id, action_taken=EditActionTaken.EDITED, chosen_target_pct=_mix(TIER1_EQUITY + 6), funded=True,
    )
    second = compute_and_log_allocation(session, USER)
    record_allocation_outcome(
        session, USER, second.event.event_id, action_taken=EditActionTaken.REJECTED, chosen_target_pct=None, funded=None,
        reason_code="dont_understand",
    )
    compute_and_log_personalization(session, USER)

    trace = get_trace(session, USER, "personalization")
    steps = next(s for s in trace.sections if s.key == "step_by_step_trace").facts
    assert steps[0].value.startswith("You set your own mix: equity +6")
    assert "invested it" in steps[0].value
    assert steps[1].value == "You turned it down because you weren't sure what it meant"
    assert steps[1].note.startswith("Not counted")

    allocation_trace = get_trace(session, USER, "allocation", event_id=second.event.event_id)
    personal = next(s for s in allocation_trace.sections if s.key == "personal_adjustment")
    assert personal.available is True
    assert "Your tier stays the same" in personal.summary


# --- validation ---


@pytest.mark.parametrize(
    "kwargs",
    [
        {"action_taken": EditActionTaken.EDITED, "chosen_target_pct": None, "funded": True},
        {"action_taken": EditActionTaken.EDITED, "chosen_target_pct": {**_mix(40), "equity": "60"}, "funded": True},
        {"action_taken": EditActionTaken.EDITED, "chosen_target_pct": {"equity": "100"}, "funded": True},
        {"action_taken": EditActionTaken.REJECTED, "chosen_target_pct": None, "funded": None},
        {"action_taken": EditActionTaken.REJECTED, "chosen_target_pct": None, "funded": None, "reason_code": "meh"},
    ],
)
def test_malformed_outcomes_are_refused(session, kwargs):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    with pytest.raises(InvalidAllocationOutcomeError):
        record_allocation_outcome(session, USER, shown.event.event_id, **kwargs)


def test_only_a_recorded_choice_can_be_marked_invested(session):
    _onboard_room_to_grow(session)
    shown = compute_and_log_allocation(session, USER)
    with pytest.raises(InvalidAllocationOutcomeError):
        mark_allocation_funded(session, USER, shown.event.event_id)
