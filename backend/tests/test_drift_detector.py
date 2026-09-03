from decimal import Decimal

from app.services.drift_detection_config import HYSTERESIS_CYCLES_TO_LOWER_TIER, HYSTERESIS_CYCLES_TO_RAISE_TIER
from app.services.drift_detector import run_drift_detection
from app.services.drift_personas import (
    Persona,
    PersonaTrace,
    SyntheticAllocationEdit,
    SyntheticSnapshot,
)
from app.services.personalization import EditActionTaken
from app.services.risk_profile import IncomeStabilityValue


def _persona(persona_id: str, start_tier: int) -> Persona:
    return Persona(
        persona_id=persona_id, name=persona_id, description="test fixture",
        ground_truth_tier_start=start_tier, ground_truth_tier_end=start_tier,
        income_stability=IncomeStabilityValue.REGULAR, dependents_count=0,
        monthly_income_paise=100_000_00, total_life_cover_paise=0,
    )


def _flat_snapshots(months: int, buffer: Decimal, emi: Decimal) -> tuple[SyntheticSnapshot, ...]:
    return tuple(SyntheticSnapshot(m, buffer, emi) for m in range(1, months + 1))


def _flat_edits(months: int, suggested_equity: Decimal, chosen_equity: Decimal) -> tuple[SyntheticAllocationEdit, ...]:
    return tuple(
        SyntheticAllocationEdit(m, suggested_equity, chosen_equity, EditActionTaken.EDITED, True)
        for m in range(1, months + 1)
    )


# Tier-3 buffer/EMI that maps to capacity ceiling 3, and tier-5 values that
# map to ceiling 5, per Module 3's rule table -- used to force a clean,
# unambiguous capacity direction without re-deriving the bands by hand
# in every test.
TIER3_BUFFER, TIER3_EMI = Decimal("3.0"), Decimal("0.35")  # ceiling 3
TIER5_BUFFER, TIER5_EMI = Decimal("8.0"), Decimal("0.05")  # ceiling 5
TIER1_BUFFER, TIER1_EMI = Decimal("0.5"), Decimal("0.55")  # ceiling 1


def test_no_deviation_anywhere_never_drifts():
    persona = _persona("flat", 3)
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(6, TIER3_BUFFER, TIER3_EMI),
        allocation_edits=_flat_edits(6, Decimal("35"), Decimal("35")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.final_detected_tier == 3
    assert result.drift_detected is False
    assert result.committed_months == ()


def test_capacity_alone_deviating_never_drifts_without_behavioral_agreement():
    # capacity says tier 5 every month; behavior stays exactly at the
    # tier-3 suggestion. Only one family ever deviates -- must never drift.
    persona = _persona("capacity_only", 3)
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(10, TIER5_BUFFER, TIER5_EMI),
        allocation_edits=_flat_edits(10, Decimal("35"), Decimal("35")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.drift_detected is False
    assert result.final_detected_tier == 3


def test_behavioral_alone_deviating_never_drifts_without_capacity_agreement():
    persona = _persona("behavior_only", 3)
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(10, TIER3_BUFFER, TIER3_EMI),
        allocation_edits=_flat_edits(10, Decimal("35"), Decimal("65")),  # way above tier-3's own target
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.drift_detected is False
    assert result.final_detected_tier == 3


def test_agreement_below_the_raise_threshold_does_not_commit():
    persona = _persona("almost_raise", 3)
    months = HYSTERESIS_CYCLES_TO_RAISE_TIER - 1
    assert months >= 1
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(months, TIER5_BUFFER, TIER5_EMI),
        allocation_edits=_flat_edits(months, Decimal("35"), Decimal("65")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.drift_detected is False


def test_agreement_at_exactly_the_raise_threshold_commits_one_tier():
    persona = _persona("exact_raise", 3)
    months = HYSTERESIS_CYCLES_TO_RAISE_TIER
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(months, TIER5_BUFFER, TIER5_EMI),
        allocation_edits=_flat_edits(months, Decimal("35"), Decimal("65")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.final_detected_tier == 4  # exactly one tier up, not straight to 5
    assert result.committed_months == (months,)


def test_agreement_at_exactly_the_lower_threshold_commits_one_tier():
    persona = _persona("exact_lower", 3)
    months = HYSTERESIS_CYCLES_TO_LOWER_TIER
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(months, TIER1_BUFFER, TIER1_EMI),
        allocation_edits=_flat_edits(months, Decimal("35"), Decimal("10")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.final_detected_tier == 2
    assert result.committed_months == (months,)


def test_lowering_needs_more_evidence_than_raising():
    assert HYSTERESIS_CYCLES_TO_LOWER_TIER > HYSTERESIS_CYCLES_TO_RAISE_TIER

    months = HYSTERESIS_CYCLES_TO_RAISE_TIER  # enough to raise, not enough to lower
    persona = _persona("asymmetry_check", 3)
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(months, TIER1_BUFFER, TIER1_EMI),
        allocation_edits=_flat_edits(months, Decimal("35"), Decimal("10")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.drift_detected is False  # would have committed if this were upward evidence


def test_sustained_reversal_eventually_resets_and_flips_the_streak_direction():
    # Behavioral evidence is read over a trailing 3-month window, so a
    # brief interruption gets smoothed rather than instantly flipping the
    # window average -- this uses a *sustained* reversal (not just one
    # neutral month) long enough to actually flush the window, and checks
    # the streak genuinely transitions rather than the original upward
    # direction silently persisting or committing early.
    persona = _persona("reversal", 3)
    # months 1-2: strongly up (2 == HYSTERESIS_CYCLES_TO_RAISE_TIER, so on
    # its own this would already commit)
    # months 3-8: strongly down, sustained long enough to fully flush the
    # up-deviating values out of the 3-month window and then build its own
    # streak in the new direction
    equities = [65, 65] + [10] * 6
    edits = tuple(SyntheticAllocationEdit(m, Decimal("35"), Decimal(str(v)), EditActionTaken.EDITED, True) for m, v in enumerate(equities, start=1))
    # capacity mirrors the same reversal so both families can agree at every stage
    buffers = [TIER5_BUFFER, TIER5_BUFFER] + [TIER1_BUFFER] * 6
    emis = [TIER5_EMI, TIER5_EMI] + [TIER1_EMI] * 6
    snapshots = tuple(SyntheticSnapshot(m, b, e) for m, (b, e) in enumerate(zip(buffers, emis), start=1))

    trace = PersonaTrace(persona, snapshots, edits, drawdown_month_index=None)
    result = run_drift_detection(trace)

    # committed up first (months 1-2, from tier 3 to 4), then reversed and
    # eventually committed back down at least once
    assert result.committed_months[0] == 2
    assert result.cycles[1].reference_tier_after == 4
    later_commits = [c for c in result.cycles if c.committed and c.month_index > 2]
    assert later_commits, "expected the sustained reversal to eventually commit a downward move"
    assert later_commits[0].reference_tier_after < later_commits[0].reference_tier_before


def test_rejections_carry_zero_weight_and_never_drive_the_behavioral_signal():
    persona = _persona("all_rejected", 3)
    edits = tuple(
        SyntheticAllocationEdit(m, Decimal("35"), None, EditActionTaken.REJECTED, None) for m in range(1, 8)
    )
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(7, TIER5_BUFFER, TIER5_EMI),  # capacity deviates...
        allocation_edits=edits,  # ...but there's no usable behavioral evidence at all
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.drift_detected is False


def test_freeze_window_suspends_evidence_accumulation_during_drawdown():
    persona = _persona("frozen", 4)
    months = 6
    snapshots = _flat_snapshots(months, TIER1_BUFFER, TIER1_EMI)  # would agree with a downward behavioral signal
    edits = _flat_edits(months, Decimal("50"), Decimal("15"))  # strongly below the tier-4 suggestion
    trace = PersonaTrace(persona, snapshots, edits, drawdown_month_index=1)  # frozen from month 1

    result = run_drift_detection(trace)
    frozen_cycles = [c for c in result.cycles if c.frozen]
    assert len(frozen_cycles) >= 1
    for c in frozen_cycles:
        assert c.committed is False
        assert c.signals == ()


def test_multi_tier_drift_shows_up_as_a_sequence_of_single_tier_commits():
    persona = _persona("multi_step", 1)
    months = HYSTERESIS_CYCLES_TO_RAISE_TIER * 3 + 2  # enough cycles for several commits
    trace = PersonaTrace(
        persona,
        snapshots=_flat_snapshots(months, TIER5_BUFFER, TIER5_EMI),
        allocation_edits=_flat_edits(months, Decimal("10"), Decimal("65")),
        drawdown_month_index=None,
    )
    result = run_drift_detection(trace)
    assert result.final_detected_tier > persona.ground_truth_tier_start
    assert len(result.committed_months) >= 2  # multiple discrete commits, not one big jump
    for c in result.cycles:
        if c.committed:
            assert abs(c.reference_tier_after - c.reference_tier_before) == 1
