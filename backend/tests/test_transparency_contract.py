"""The contract between a decision producer and its Module 9 spec.

Module 9's `required_*_keys` are a hand-written description of what each
producing service stores. Nothing in the type system links
`DECISION_TYPES["risk_profile"].required_suggested_value_keys` to the dict
literal in `risk_profile_service.compute_and_log_risk_tier`. Rename a key
on one side and there is no error, no crash and no failing test -- just
every newly produced event quietly reporting `gap_detected=True` forever,
which is the most expensive possible failure mode because it looks like
working gap detection.

These tests close that loop the only way that actually holds: run each
producer for real, then assert the event it just wrote satisfies its own
spec with nothing missing. A rename on either side now fails here.
"""

import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import HoldingType
from app.services.debt_leak_service import compute_and_log_debt_leak_report
from app.services.event_log import get_user_event_history
from app.services.financial_position import ExpenseFrequency
from app.services.gamification_service import check_milestones
from app.services.onboarding import add_emi, add_expense_item, add_holding, upsert_profile
from app.services.personalization_service import compute_and_log_personalization
from app.services.risk_profile_service import compute_and_log_risk_tier
from app.services.transparency import DECISION_TYPES, _missing_fields, build_trace

USER = "contract-user-1"

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "significant",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
}


@pytest.fixture()
def produced(session):
    """Run every in-backend decision producer for real, once."""
    upsert_profile(
        session,
        user_id=USER,
        income_paise=100_000_00,
        income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED,
        dependents_count=0,
        cash_balance_paise=800_000_00,
    )
    add_expense_item(
        session, user_id=USER, category="Rent", amount_paise=20_000_00,
        frequency=ExpenseFrequency.MONTHLY, is_essential=True,
    )
    add_holding(
        session, user_id=USER, description="Equity fund", value_paise=100_000_00,
        holding_type=HoldingType.EQUITY_MUTUAL_FUND,
    )
    add_emi(
        session, user_id=USER, lender="Personal Loan Co", amount_paise=10_000_00,
        remaining_tenure_months=24, annual_rate_bps=1500,
    )
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)
    compute_and_log_allocation(session, USER)
    compute_and_log_debt_leak_report(session, USER)
    compute_and_log_personalization(session, USER)
    check_milestones(session, USER)
    return session


#: Decision types whose producer lives in this backend and can be run here.
#: Module 5's two engines are excluded: one calls an external n8n webhook,
#: the other needs the research module's dependencies. Both are covered by
#: their own contract tests (see test_rumour_local_engine_contract.py).
IN_BACKEND_DECISION_TYPES = (
    "risk_profile",
    "allocation",
    "debt_leak_engine",
    "personalization",
    "gamification",
)


@pytest.mark.parametrize("module_source", IN_BACKEND_DECISION_TYPES)
def test_freshly_produced_event_satisfies_its_own_spec(produced, module_source):
    session = produced
    spec = DECISION_TYPES[module_source]
    events = get_user_event_history(session, USER, module_source=module_source, limit=1)
    assert events, f"{module_source} producer wrote no event -- fixture is wrong, not the spec"

    missing = _missing_fields(events[0], spec)
    assert missing == (), (
        f"{module_source}: the producing service no longer stores {list(missing)}, which its "
        "DecisionTypeSpec still requires. Either the producer dropped a field or the spec's "
        "required-key list drifted -- fix one of the two; do not relax this assertion."
    )


@pytest.mark.parametrize("module_source", IN_BACKEND_DECISION_TYPES)
def test_freshly_produced_event_builds_a_gapless_trace(produced, module_source):
    """The stronger form of the same check: not merely that the keys exist,
    but that every reasoning section actually renders from them."""
    session = produced
    spec = DECISION_TYPES[module_source]
    event = get_user_event_history(session, USER, module_source=module_source, limit=1)[0]

    trace = build_trace(event, spec)

    assert trace.gap_detected is False, f"{module_source} missing {list(trace.missing_fields)}"
    unavailable = [s.key for s in trace.sections if not s.available]
    assert unavailable == [], f"{module_source} sections could not render: {unavailable}"
    assert "Cannot fully reconstruct" not in trace.headline


def test_every_registered_spec_is_covered_by_a_contract_test():
    """A new DecisionTypeSpec must not be able to slip in without someone
    deciding how its producer gets contract-tested."""
    externally_produced = {"rumour_verification", "rumour_verification_local"}
    covered = set(IN_BACKEND_DECISION_TYPES) | externally_produced
    assert set(DECISION_TYPES) == covered, (
        "DECISION_TYPES changed. Add the new type to IN_BACKEND_DECISION_TYPES if its producer "
        "runs in this backend, or to `externally_produced` with its own contract test."
    )


def test_every_section_declares_at_least_one_required_field():
    """A section requiring nothing can never be flagged as a gap, so it would
    render from whatever happened to be stored -- the exact silent-fabrication
    failure this module exists to prevent."""
    for module_source, spec in DECISION_TYPES.items():
        for section in spec.sections:
            assert section.requires_value or section.requires_context, (
                f"{module_source}.{section.key} declares no required fields"
            )
