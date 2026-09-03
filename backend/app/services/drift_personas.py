"""Module 8: synthetic personas and hand-authored trace generation.

SIMULATED ONLY -- every number in this file is hand-authored to express a
particular behavioural signature, not sampled or derived from any real
user. Shapes mirror the real schemas it depends on: `SyntheticAllocationEdit`
mirrors a `module_source="allocation"` suggestion_event once an outcome is
recorded (Module 1's shape, Module 7's evidence weighting), and
`SyntheticSnapshot` mirrors a `user_monthly_snapshot` row (Module 1/2's
shape). Deterministic and hand-written rather than randomly sampled, so
every persona's trace is exactly reproducible and each number is traceable
to the behavioural story it's meant to tell.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.personalization import EditActionTaken
from app.services.risk_profile import IncomeStabilityValue

EDITED = EditActionTaken.EDITED
ACCEPTED = EditActionTaken.ACCEPTED
REJECTED = EditActionTaken.REJECTED
IGNORED = EditActionTaken.IGNORED


@dataclass(frozen=True)
class SyntheticSnapshot:
    """Shaped like a user_monthly_snapshot row (the two fields the
    capacity signal needs; income/surplus/cash aren't used by drift
    detection)."""

    month_index: int
    buffer_coverage_months: Decimal
    debt_to_income_ratio: Decimal


@dataclass(frozen=True)
class SyntheticAllocationEdit:
    """Shaped like a module_source="allocation" suggestion_event with a
    recorded outcome: suggested_value.target_pct.equity, chosen_value.equity
    (or None), action_taken, funded."""

    month_index: int
    suggested_equity_pct: Decimal
    chosen_equity_pct: Decimal | None
    action_taken: EditActionTaken
    funded: bool | None


@dataclass(frozen=True)
class Persona:
    persona_id: str
    name: str
    description: str
    ground_truth_tier_start: int
    ground_truth_tier_end: int
    income_stability: IncomeStabilityValue
    dependents_count: int
    monthly_income_paise: int
    total_life_cover_paise: int


@dataclass(frozen=True)
class PersonaTrace:
    persona: Persona
    snapshots: tuple[SyntheticSnapshot, ...]
    allocation_edits: tuple[SyntheticAllocationEdit, ...]
    drawdown_month_index: int | None


# --- Persona 1: Steady Conservative -- negative control, no drift ---
# Capacity genuinely matches tier 1 throughout (thin buffer); behavior
# stays right at the tier-1 suggestion every month. Nothing should move.

PERSONA_STEADY_CONSERVATIVE = Persona(
    persona_id="steady_conservative",
    name="Steady Conservative",
    description="Genuinely tier-1 by both capacity and revealed preference, unchanging for a year. Tests that stability produces no false drift.",
    ground_truth_tier_start=1,
    ground_truth_tier_end=1,
    income_stability=IncomeStabilityValue.REGULAR,
    dependents_count=0,
    monthly_income_paise=50_000_00,
    total_life_cover_paise=0,
)


def _trace_steady_conservative() -> PersonaTrace:
    snapshots = tuple(SyntheticSnapshot(m, Decimal("0.8"), Decimal("0.15")) for m in range(1, 13))
    chosen = [None, Decimal("11"), None, Decimal("9"), None, None, Decimal("11"), None, Decimal("9"), None, None, Decimal("10")]
    edits = tuple(
        SyntheticAllocationEdit(m, Decimal("10"), chosen[m - 1], ACCEPTED if chosen[m - 1] is None else EDITED, True)
        for m in range(1, 13)
    )
    return PersonaTrace(PERSONA_STEADY_CONSERVATIVE, snapshots, edits, drawdown_month_index=None)


# --- Persona 2: Windfall Riser -- upward drift, capped by revealed
# behavior at tier 4 even though capacity would allow tier 5 ---

PERSONA_WINDFALL_RISER = Persona(
    persona_id="windfall_riser",
    name="Windfall Riser",
    description="Starts tier 2. A raise + debt payoff around month 6 lifts capacity to tier-5 territory, and behavior trends up in step -- but plateaus at tier-4 level, so the detector should stop there, not chase capacity alone.",
    ground_truth_tier_start=2,
    ground_truth_tier_end=4,
    income_stability=IncomeStabilityValue.REGULAR,
    dependents_count=0,
    monthly_income_paise=100_000_00,
    total_life_cover_paise=0,
)


def _trace_windfall_riser() -> PersonaTrace:
    buffers = [1.5, 1.4, 1.6, 1.5, 1.6, 2.5, 3.5, 4.5, 5.5, 6.0, 6.2, 6.5]
    emis = [0.42, 0.43, 0.41, 0.42, 0.40, 0.35, 0.30, 0.25, 0.19, 0.18, 0.17, 0.16]
    chosen = [19, 21, 20, 22, 20, 30, 38, 44, 48, 49, 50, 49]

    snapshots = tuple(SyntheticSnapshot(m, Decimal(str(buffers[m - 1])), Decimal(str(emis[m - 1]))) for m in range(1, 13))
    edits = tuple(SyntheticAllocationEdit(m, Decimal("20"), Decimal(str(chosen[m - 1])), EDITED, True) for m in range(1, 13))
    return PersonaTrace(PERSONA_WINDFALL_RISER, snapshots, edits, drawdown_month_index=None)


# --- Persona 3: Debt Spiral Faller -- downward drift over 15 months,
# exercising the asymmetric (slower) hysteresis for lowering a tier ---

PERSONA_DEBT_SPIRAL_FALLER = Persona(
    persona_id="debt_spiral_faller",
    name="Debt Spiral Faller",
    description="Starts tier 4. New debt and a shrinking buffer from month 6 onward drag both capacity and revealed behavior down to tier 2 by month 15 -- slower to detect than the equivalent rise, by design (HYSTERESIS_CYCLES_TO_LOWER_TIER > _TO_RAISE_TIER).",
    ground_truth_tier_start=4,
    ground_truth_tier_end=2,
    income_stability=IncomeStabilityValue.REGULAR,
    dependents_count=0,
    monthly_income_paise=80_000_00,
    total_life_cover_paise=0,
)


def _trace_debt_spiral_faller() -> PersonaTrace:
    buffers = [5.0, 5.0, 5.0, 5.0, 5.0, 4.0, 3.0, 2.2, 1.6, 1.2, 1.0, 0.9, 0.8, 0.7, 0.7]
    emis = [0.22, 0.22, 0.22, 0.22, 0.22, 0.28, 0.33, 0.38, 0.42, 0.46, 0.48, 0.50, 0.51, 0.52, 0.53]
    chosen = [48, 52, 50, 49, 51, 45, 38, 32, 26, 22, 20, 18, 16, 15, 15]

    snapshots = tuple(SyntheticSnapshot(m, Decimal(str(buffers[m - 1])), Decimal(str(emis[m - 1]))) for m in range(1, 16))
    edits = tuple(SyntheticAllocationEdit(m, Decimal("50"), Decimal(str(chosen[m - 1])), EDITED, True) for m in range(1, 16))
    return PersonaTrace(PERSONA_DEBT_SPIRAL_FALLER, snapshots, edits, drawdown_month_index=None)


# --- Persona 4: Confused Middle -- noisy, contradictory edits with flat,
# tier-matching capacity throughout; no drift, since capacity alone never
# deviates and agreement needs both families ---

PERSONA_CONFUSED_MIDDLE = Persona(
    persona_id="confused_middle",
    name="Confused Middle",
    description="Tier-3 capacity holds flat all year while behavior swings erratically (rejections, ignored suggestions, alternating extreme edits) -- tests that noisy single-family signals never accumulate into drift.",
    ground_truth_tier_start=3,
    ground_truth_tier_end=3,
    income_stability=IncomeStabilityValue.REGULAR,
    dependents_count=0,
    monthly_income_paise=70_000_00,
    total_life_cover_paise=0,
)


def _trace_confused_middle() -> PersonaTrace:
    snapshots = tuple(SyntheticSnapshot(m, Decimal("3.0"), Decimal("0.35")) for m in range(1, 13))

    pattern = [
        (EDITED, Decimal("60"), True),
        (REJECTED, None, None),
        (EDITED, Decimal("12"), True),
        (IGNORED, None, None),
        (EDITED, Decimal("55"), False),
        (REJECTED, None, None),
        (EDITED, Decimal("15"), True),
        (IGNORED, None, None),
        (EDITED, Decimal("58"), True),
        (REJECTED, None, None),
        (EDITED, Decimal("10"), False),
        (ACCEPTED, None, True),
    ]
    edits = tuple(
        SyntheticAllocationEdit(m, Decimal("35"), pattern[m - 1][1], pattern[m - 1][0], pattern[m - 1][2])
        for m in range(1, 13)
    )
    return PersonaTrace(PERSONA_CONFUSED_MIDDLE, snapshots, edits, drawdown_month_index=None)


# --- Persona 5: Market Panic Then Recovery -- tests the drawdown freeze
# window specifically: a transient panic right after a simulated drawdown
# must NOT register as drift, even though (without the freeze) the panic
# months alone would show two-family agreement ---

PERSONA_MARKET_PANIC_RECOVERY = Persona(
    persona_id="market_panic_recovery",
    name="Market Panic Then Recovery",
    description="Tier-4 all year. A simulated drawdown at month 6 triggers 3 months of panicked, conservative edits plus a coincident capacity dip -- without the freeze window this accumulates enough agreeing evidence to commit a spurious downward re-tier (which then reverses again once behavior recovers); the freeze window suppresses it entirely, and the persona should show zero commits, ending at tier 4.",
    ground_truth_tier_start=4,
    ground_truth_tier_end=4,
    income_stability=IncomeStabilityValue.REGULAR,
    dependents_count=0,
    monthly_income_paise=90_000_00,
    total_life_cover_paise=0,
)


def _trace_market_panic_recovery() -> PersonaTrace:
    # Panic spans exactly HYSTERESIS_CYCLES_TO_LOWER_TIER (3) months
    # (6-8), with a sharp recovery from month 9. Without the freeze
    # window, the 3 panic months alone accumulate enough agreeing
    # evidence to commit a downward re-tier at month 9 -- which then
    # reverses again once behavior recovers, a spurious round-trip. With
    # the freeze covering months 6-7, only one non-frozen panic month (8)
    # is left before recovery arrives at month 9, one short of the
    # threshold: verified directly in test_drift_evaluation.py by running
    # this exact trace with and without a drawdown flag and comparing.
    buffers = [5, 5, 5, 5, 5, 2.5, 2.2, 2.0, 5, 5, 5, 5]
    emis = [0.22] * 5 + [0.35, 0.36, 0.38] + [0.22] * 4
    chosen = [50, 50, 50, 50, 50, 20, 18, 15, 50, 50, 50, 50]

    snapshots = tuple(SyntheticSnapshot(m, Decimal(str(buffers[m - 1])), Decimal(str(emis[m - 1]))) for m in range(1, 13))
    edits = tuple(SyntheticAllocationEdit(m, Decimal("50"), Decimal(str(chosen[m - 1])), EDITED, True) for m in range(1, 13))
    return PersonaTrace(PERSONA_MARKET_PANIC_RECOVERY, snapshots, edits, drawdown_month_index=6)


ALL_PERSONA_TRACES = (
    _trace_steady_conservative(),
    _trace_windfall_riser(),
    _trace_debt_spiral_faller(),
    _trace_confused_middle(),
    _trace_market_panic_recovery(),
)
