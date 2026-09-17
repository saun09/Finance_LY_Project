"""Every trace a user reads must be in plain language.

The transparency layer originally rendered stored values verbatim, which
produced screens reading `horizon: gt_15y`, `drawdown_reaction:
buy_a_lot` and `emi_to_income_ratio: 0.3`. That is faithful and
unreadable at the same time, and transparency a person cannot read is not
transparency.

These tests are the regression guard for that. They assert the *user-
facing* strings -- headlines, section summaries and fact labels/values --
contain no raw enum codes, no snake_case field names and no unexplained
internal identifiers, while the stored value stays reachable on the Fact
underneath. A future decision type added without a `facts` builder, or a
builder that leaks a code, fails here.
"""

import re

import pytest

from app.models.onboarding import EmploymentType, IncomeStability
from app.services.allocation_service import compute_and_log_allocation
from app.services.asset_classification_config import HoldingType
from app.services.debt_leak_service import compute_and_log_debt_leak_report
from app.services.financial_position import ExpenseFrequency
from app.services.gamification_service import check_milestones
from app.services.onboarding import add_emi, add_expense_item, add_holding, upsert_profile
from app.services.personalization_service import compute_and_log_personalization
from app.services.risk_profile_service import compute_and_log_risk_tier
from app.services import transparency_labels as L
from app.services.transparency import DECISION_TYPES, get_trace

USER = "readability-user-1"

AGGRESSIVE_ANSWERS = {
    "horizon": "gt_15y",
    "drawdown_reaction": "buy_a_lot",
    "experience": "extensive",
    "goal": "maximize",
    "windfall_allocation": "equity_plus_borrow",
    "sure_gain_tradeoff": "chance_10pct_50000",
    "friend_description": "real_gambler",
}

#: Codes that must never reach a user-facing string. Each is a real value
#: that appeared on the old screens.
FORBIDDEN_CODES = (
    "gt_15y", "buy_a_lot", "real_gambler", "chance_10pct_50000",
    "equity_plus_borrow", "manual_only", "equity_mutual_fund",
    "official_exchange_filing", "semi_liquid", "not_yet_due",
    "capacity_unlock", "source_authority", "emi_to_income_ratio",
    "buffer_coverage_months", "total_life_cover_paise",
)

#: A user-facing string should not contain snake_case identifiers at all.
SNAKE_CASE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


@pytest.fixture()
def traced(session):
    upsert_profile(
        session, user_id=USER, income_paise=60_000_00,
        income_stability=IncomeStability.REGULAR, employment_type=EmploymentType.SALARIED,
        dependents_count=0, cash_balance_paise=500_000_00,
    )
    add_expense_item(
        session, user_id=USER, category="Rent", amount_paise=20_000_00,
        frequency=ExpenseFrequency.MONTHLY, is_essential=True,
    )
    add_emi(
        session, user_id=USER, lender="Car Loan", amount_paise=18_000_00,
        remaining_tenure_months=36, annual_rate_bps=1100,
    )
    add_holding(
        session, user_id=USER, description="Equity fund", value_paise=100_000_00,
        holding_type=HoldingType.EQUITY_MUTUAL_FUND,
    )
    compute_and_log_risk_tier(session, USER, AGGRESSIVE_ANSWERS)
    compute_and_log_allocation(session, USER)
    compute_and_log_debt_leak_report(session, USER)
    compute_and_log_personalization(session, USER)
    check_milestones(session, USER)
    return session


IN_BACKEND = ("risk_profile", "allocation", "debt_leak_engine", "personalization", "gamification")


def _user_facing_strings(trace) -> list[str]:
    """Everything a person actually reads. Deliberately excludes `Fact.raw`,
    which is the stored value and is *supposed* to be a code."""
    out = [trace.headline, trace.display_name]
    for section in trace.sections:
        out.append(section.title)
        if section.summary:
            out.append(section.summary)
        for f in section.facts:
            out.extend([f.label, f.value])
            if f.note:
                out.append(f.note)
    return [s for s in out if s]


@pytest.mark.parametrize("module_source", IN_BACKEND)
def test_every_section_produces_readable_rows(traced, module_source):
    trace = get_trace(traced, USER, module_source)
    assert trace.gap_detected is False
    for section in trace.sections:
        assert section.summary, f"{module_source}.{section.key} has no plain-English summary"
        assert section.facts, f"{module_source}.{section.key} produced no readable rows"
        for f in section.facts:
            assert f.label and f.value, f"{module_source}.{section.key} has an empty row"


@pytest.mark.parametrize("module_source", IN_BACKEND)
def test_no_raw_enum_code_reaches_a_user_facing_string(traced, module_source):
    trace = get_trace(traced, USER, module_source)
    for text in _user_facing_strings(trace):
        for code in FORBIDDEN_CODES:
            assert code not in text, f"{module_source}: user-facing text leaks {code!r}: {text!r}"


@pytest.mark.parametrize("module_source", IN_BACKEND)
def test_no_snake_case_identifier_reaches_a_label_or_value(traced, module_source):
    """Notes may quote a config path (the leak engine's scope note names
    `expense_source_decision.py`), but a label or value never should."""
    trace = get_trace(traced, USER, module_source)
    for section in trace.sections:
        for f in section.facts:
            for text in (f.label, f.value):
                assert not SNAKE_CASE.search(text), (
                    f"{module_source}.{section.key}: {text!r} still reads as a field name"
                )


def test_the_questionnaire_is_shown_as_the_questions_actually_asked(traced):
    trace = get_trace(traced, USER, "risk_profile")
    questionnaire = next(s for s in trace.sections if s.key == "questionnaire")
    labels = [f.label for f in questionnaire.facts]
    values = [f.value for f in questionnaire.facts]

    assert "When will you need most of this money?" in labels
    assert "More than 15 years" in values
    # and the stored code is still reachable underneath
    horizon = next(f for f in questionnaire.facts if f.label.startswith("When will you need"))
    assert horizon.raw == "gt_15y"


def test_answers_are_translated_with_the_version_that_was_recorded():
    """Translating an old event with today's questionnaire would put words
    in the user's mouth they were never shown."""
    assert L.answer_label("v1", "horizon", "gt_15y") == "More than 15 years"
    # a code the recorded version never offered falls back, never guesses
    assert L.answer_label("v1", "horizon", "made_up_option") == "made_up_option"
    assert L.answer_label("nonexistent_version", "horizon", "gt_15y") == "gt_15y"


def test_the_cap_is_explained_in_words_not_codes(traced):
    trace = get_trace(traced, USER, "risk_profile")
    assert "EMIs" in trace.headline
    assert "emi_to_income_ratio" not in trace.headline
    outcome = next(s for s in trace.sections if s.key == "outcome")
    blocker = next(f for f in outcome.facts if f.label == "What's holding you back")
    # sentence-cased, not str.capitalize() which would render "EMIs" as "emis"
    assert blocker.value == "How much of your income goes to EMIs"
    assert blocker.raw == "emi_to_income_ratio"


def test_money_reads_as_rupees_and_ratios_as_percentages(traced):
    trace = get_trace(traced, USER, "risk_profile")
    capacity = next(s for s in trace.sections if s.key == "capacity_layer")
    income = next(f for f in capacity.facts if f.label == "Monthly income")
    assert income.value == "₹60,000"
    assert income.raw == "6000000"

    emi = next(f for f in capacity.facts if f.label == "Share of income going to EMIs")
    assert emi.value.endswith("%")
    assert "0.3" not in emi.value


def test_raw_is_only_carried_when_it_differs_from_what_is_shown(traced):
    """"stored as" on a value that was already plain is clutter, not rigor."""
    for module_source in IN_BACKEND:
        trace = get_trace(traced, USER, module_source)
        for section in trace.sections:
            for f in section.facts:
                assert f.raw != f.value, f"{module_source}: redundant raw on {f.label!r}"


def test_tiers_are_named_not_just_numbered(traced):
    trace = get_trace(traced, USER, "risk_profile")
    assert "Tier" in trace.headline
    assert any(name in trace.headline for name in L.TIER_LABEL.values())


def test_every_registered_spec_declares_readable_builders():
    """A new decision type cannot ship as a raw key/value dump."""
    for module_source, spec in DECISION_TYPES.items():
        for section in spec.sections:
            assert section.facts is not None, f"{module_source}.{section.key} has no facts builder"
            assert section.summary is not None, f"{module_source}.{section.key} has no summary"


def test_a_partially_recorded_section_produces_no_confident_sentence(traced):
    """Readable rows are built over verified inputs only -- a half-recorded
    section must degrade to its raw values, not to a fluent sentence
    written over gaps."""
    from app.services.event_log import log_suggestion_event

    log_suggestion_event(
        traced, user_id=USER, module_source="gamification",
        suggested_value={"milestone_id": "m1", "category": "buffer", "headline": "Something"},
        market_context={},  # missing config_version
    )
    trace = get_trace(traced, USER, "gamification")
    section = trace.sections[0]
    assert section.available is False
    assert section.facts == ()
    assert section.summary is None


def test_an_unrecorded_field_is_named_in_words_not_as_a_key(traced):
    """The app has no raw-record view any more, so a gap has to be
    describable on its own terms. `unlock_conditions` on screen would tell a
    reader nothing about what is missing."""
    from app.services.event_log import log_suggestion_event

    log_suggestion_event(
        traced, user_id=USER, module_source="risk_profile",
        suggested_value={"stated_tier": 5, "final_tier": 3, "capped": True},
        market_context={},
    )
    trace = get_trace(traced, USER, "risk_profile")
    assert trace.gap_detected is True

    assert trace.missing_field_labels
    assert len(trace.missing_field_labels) == len(trace.missing_fields)
    for label in trace.missing_field_labels:
        assert not SNAKE_CASE.search(label), f"{label!r} still reads as a field name"

    outcome = next(s for s in trace.sections if s.key == "outcome")
    assert "What's holding you back" in outcome.missing_field_labels
    assert "How to lift your tier" in outcome.missing_field_labels
    # the machine-readable names are still there for anyone auditing
    assert "unlock_conditions" in outcome.missing_fields
