"""Module 8: pure simulated behavioural-drift detector. No I/O, no model
call — everything here is a deterministic function of the synthetic trace
data defined in drift_personas.py.

SIMULATED ONLY. This module has never been evaluated against real user
behaviour, and nothing here should be read, quoted, or represented as if
it had been — see drift_evaluation.py and backend/README.md's "future
work: real-user validation" note.

Two independent signal families feed each review cycle:

- capacity: Module 3's own compute_capacity_ceiling, applied to
  trailing-window-averaged snapshot data (buffer months, EMI-to-income
  ratio) — reused directly, not reimplemented, so drift detection is
  consistent with the same rule table Module 3 uses live.
- behavioral: an evidence-weighted average of chosen equity % from
  allocation-suggestion outcomes over a trailing window, using the same
  evidence_weight function Module 7 uses for personalization (funded
  edit=1.0, unfunded acceptance=0.5, rejection/ignored=0.0) — reused
  directly for the same reason.

A cycle only counts as candidate drift evidence when BOTH families deviate
from the current reference tier in the SAME direction (MIN_AGREEING_SIGNAL_FAMILIES
enforced literally: with exactly two families defined, "agreeing" means
both, not just one). Hysteresis then requires that agreement to repeat
across consecutive cycles (asymmetric: fewer cycles to raise, more to
lower) before the reference tier actually moves — one tier per commit,
so a multi-tier drift shows up as a sequence of commits, not one jump. A
freeze window after a simulated market drawdown suspends evidence
accumulation entirely (pausing, not resetting, any streak already built).
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.allocation_config import TARGET_ALLOCATION_TABLE_V1
from app.services.asset_classification_config import AssetClass
from app.services.drift_detection_config import (
    BEHAVIORAL_SIGNAL_DEADBAND_PCT,
    BEHAVIORAL_SIGNAL_WINDOW_MONTHS,
    CAPACITY_SIGNAL_WINDOW_MONTHS,
    DRAWDOWN_FREEZE_WINDOW_CYCLES,
    HYSTERESIS_CYCLES_TO_LOWER_TIER,
    HYSTERESIS_CYCLES_TO_RAISE_TIER,
    MIN_AGREEING_SIGNAL_FAMILIES,
)
from app.services.drift_personas import PersonaTrace, SyntheticAllocationEdit, SyntheticSnapshot
from app.services.personalization import evidence_weight
from app.services.risk_profile import CapacityInputs, IncomeStabilityValue, compute_capacity_ceiling


def _equity_target(tier: int) -> Decimal:
    return TARGET_ALLOCATION_TABLE_V1[tier][AssetClass.EQUITY]


@dataclass(frozen=True)
class SignalReading:
    family: str  # "capacity" | "behavioral"
    signal_tier_estimate: int
    direction: int  # -1, 0, +1 relative to the reference tier at this cycle
    detail: str


@dataclass(frozen=True)
class ReviewCycleResult:
    month_index: int
    frozen: bool
    reference_tier_before: int
    signals: tuple[SignalReading, ...]
    agreeing_direction: int | None  # None unless >= MIN_AGREEING_SIGNAL_FAMILIES agree on a nonzero direction
    streak_direction: int | None
    streak_length: int
    committed: bool
    reference_tier_after: int


@dataclass(frozen=True)
class DriftDetectionResult:
    persona_id: str
    starting_tier: int
    final_detected_tier: int
    cycles: tuple[ReviewCycleResult, ...]
    drift_detected: bool
    committed_months: tuple[int, ...]


def _capacity_signal(
    snapshots_window: list[SyntheticSnapshot],
    income_stability: IncomeStabilityValue,
    dependents_count: int,
    monthly_income_paise: int,
    total_life_cover_paise: int,
    reference_tier: int,
) -> SignalReading:
    avg_buffer = sum(s.buffer_coverage_months for s in snapshots_window) / len(snapshots_window)
    avg_emi_ratio = sum(s.debt_to_income_ratio for s in snapshots_window) / len(snapshots_window)

    inputs = CapacityInputs(
        buffer_coverage_months=avg_buffer,
        emi_to_income_ratio=avg_emi_ratio,
        income_stability=income_stability,
        dependents_count=dependents_count,
        total_life_cover_paise=total_life_cover_paise,
        monthly_income_paise=monthly_income_paise,
        cash_balance_paise=0,  # not used by compute_capacity_ceiling
        essential_monthly_expense_paise=0,  # not used by compute_capacity_ceiling
        total_monthly_emi_paise=0,  # not used by compute_capacity_ceiling
    )
    ceiling = compute_capacity_ceiling(inputs).ceiling
    direction = 0 if ceiling == reference_tier else (1 if ceiling > reference_tier else -1)
    return SignalReading(
        family="capacity",
        signal_tier_estimate=ceiling,
        direction=direction,
        detail=f"trailing capacity ceiling={ceiling} (avg buffer={avg_buffer:.2f}mo, avg EMI ratio={avg_emi_ratio:.2%})",
    )


def _behavioral_signal(edits_window: list[SyntheticAllocationEdit], reference_tier: int) -> SignalReading:
    scored = [(e, evidence_weight(e.action_taken, e.funded)) for e in edits_window]
    weight_sum = sum(w for _, w in scored)

    reference_target = _equity_target(reference_tier)
    if weight_sum == 0:
        return SignalReading(
            family="behavioral", signal_tier_estimate=reference_tier, direction=0,
            detail="no weighted evidence in window",
        )

    weighted_avg_equity = sum((e.chosen_equity_pct if e.chosen_equity_pct is not None else e.suggested_equity_pct) * w for e, w in scored) / weight_sum
    diff = weighted_avg_equity - reference_target

    if abs(diff) < BEHAVIORAL_SIGNAL_DEADBAND_PCT:
        direction = 0
    else:
        direction = 1 if diff > 0 else -1

    return SignalReading(
        family="behavioral",
        signal_tier_estimate=reference_tier,  # direction is what matters; see module docstring
        direction=direction,
        detail=f"weighted avg chosen equity={weighted_avg_equity:.2f}% vs reference tier target={reference_target}% (diff={diff:+.2f})",
    )


def run_drift_detection(trace: PersonaTrace) -> DriftDetectionResult:
    reference_tier = trace.persona.ground_truth_tier_start
    streak_direction: int | None = None
    streak_length = 0
    cycles: list[ReviewCycleResult] = []
    committed_months: list[int] = []

    for snapshot in trace.snapshots:
        t = snapshot.month_index

        frozen = trace.drawdown_month_index is not None and trace.drawdown_month_index <= t < trace.drawdown_month_index + DRAWDOWN_FREEZE_WINDOW_CYCLES

        if frozen:
            cycles.append(
                ReviewCycleResult(
                    month_index=t, frozen=True, reference_tier_before=reference_tier, signals=(),
                    agreeing_direction=None, streak_direction=streak_direction, streak_length=streak_length,
                    committed=False, reference_tier_after=reference_tier,
                )
            )
            continue

        capacity_window = [s for s in trace.snapshots if t - CAPACITY_SIGNAL_WINDOW_MONTHS < s.month_index <= t]
        capacity_reading = _capacity_signal(
            capacity_window, trace.persona.income_stability, trace.persona.dependents_count,
            trace.persona.monthly_income_paise, trace.persona.total_life_cover_paise, reference_tier,
        )

        behavioral_window = [e for e in trace.allocation_edits if t - BEHAVIORAL_SIGNAL_WINDOW_MONTHS < e.month_index <= t]
        behavioral_reading = _behavioral_signal(behavioral_window, reference_tier)

        signals = (capacity_reading, behavioral_reading)
        nonzero_directions = [s.direction for s in signals if s.direction != 0]
        agreeing_direction = None
        if len(nonzero_directions) >= MIN_AGREEING_SIGNAL_FAMILIES and len(set(nonzero_directions)) == 1:
            agreeing_direction = nonzero_directions[0]

        if agreeing_direction is None:
            streak_direction, streak_length = None, 0
        elif agreeing_direction == streak_direction:
            streak_length += 1
        else:
            streak_direction, streak_length = agreeing_direction, 1

        threshold = HYSTERESIS_CYCLES_TO_RAISE_TIER if streak_direction == 1 else HYSTERESIS_CYCLES_TO_LOWER_TIER
        committed = False
        new_reference = reference_tier
        if streak_direction is not None and streak_length >= threshold:
            new_reference = max(1, min(5, reference_tier + streak_direction))
            if new_reference != reference_tier:
                committed = True
                committed_months.append(t)
            streak_direction, streak_length = None, 0  # reset and keep monitoring for further drift

        cycles.append(
            ReviewCycleResult(
                month_index=t, frozen=False, reference_tier_before=reference_tier, signals=signals,
                agreeing_direction=agreeing_direction, streak_direction=streak_direction, streak_length=streak_length,
                committed=committed, reference_tier_after=new_reference,
            )
        )
        reference_tier = new_reference

    return DriftDetectionResult(
        persona_id=trace.persona.persona_id,
        starting_tier=trace.persona.ground_truth_tier_start,
        final_detected_tier=reference_tier,
        cycles=tuple(cycles),
        drift_detected=reference_tier != trace.persona.ground_truth_tier_start,
        committed_months=tuple(committed_months),
    )
