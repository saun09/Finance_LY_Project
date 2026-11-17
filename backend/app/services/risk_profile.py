"""Module 3: risk profiling. Pure, deterministic, unit-tested — no I/O, no
model calls, matching the project's convention for scoring/cap logic.

Two independent scores feed the final tier:

- `compute_stated_tier`: a deterministic weighted-sum questionnaire score,
  reflecting stated *willingness*.
- `compute_capacity_ceiling`: a rule-table-driven ceiling computed only
  from objective Module 2 data (buffer months, EMI-to-income ratio, income
  stability, insurance adequacy relative to dependents), reflecting
  objective *ability*.

`compute_final_tier` enforces "ability before willingness" as the literal
formula final = min(stated, capacity_ceiling) — never the other way
around, and never a blend. When capacity binds, `compute_final_tier` also
returns which constraint(s) are binding and the exact, numeric change that
would lift each one, computed from the same real inputs.
"""

from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, Decimal
from enum import Enum

from app.services.risk_profile_config import (
    CAPACITY_RULE_TABLE_V1,
    QUESTIONNAIRE_V1,
    Band,
    CapacityRuleTable,
    Questionnaire,
)


class IncomeStabilityValue(str, Enum):
    REGULAR = "regular"
    IRREGULAR = "irregular"


# --- stated tier (willingness) ---


@dataclass(frozen=True)
class StatedTierResult:
    questionnaire_version: str
    score: int
    tier: int
    # "deterministic" for the normal weighted-sum formula below; a model
    # version string (e.g. "rf_classifier_reduced_4items_v1") when this
    # tier instead came from the quick-mode ML model, because the user
    # answered only the 4 main questions rather than all 7 -- callers use
    # this to show an "estimated" label instead of presenting it with the
    # same certainty as a full deterministic score. Defaulted so every
    # existing call site is unaffected.
    estimation_method: str = "deterministic"


def compute_stated_tier(answers: dict[str, str], questionnaire: Questionnaire = QUESTIONNAIRE_V1) -> StatedTierResult:
    missing = [q.id for q in questionnaire.questions if q.id not in answers]
    if missing:
        raise ValueError(f"missing answers for questions: {missing}")

    score = sum(questionnaire.option_points(q.id, answers[q.id]) * q.weight for q in questionnaire.questions)

    tier = 1
    for breakpoint in questionnaire.tier_breakpoints:
        if score >= breakpoint:
            tier += 1
    return StatedTierResult(questionnaire_version=questionnaire.version, score=score, tier=tier)


def stated_tier_from_ml_estimate(predicted_tier: int, model_version: str, questionnaire_version: str) -> StatedTierResult:
    """A stated-tier result sourced from the reduced-4-item ML model
    instead of the deterministic weighted-sum formula above, for when a
    user answers only the 4 main questions. `score` has no weighted-sum
    meaning here (no formula ran over partial answers) and is kept at 0;
    `estimation_method` carries the model version so this is never
    mistaken for a precise score downstream."""
    return StatedTierResult(questionnaire_version=questionnaire_version, score=0, tier=predicted_tier, estimation_method=model_version)


# --- capacity ceiling (ability) ---


@dataclass(frozen=True)
class CapacityInputs:
    buffer_coverage_months: Decimal
    emi_to_income_ratio: Decimal
    income_stability: IncomeStabilityValue
    dependents_count: int
    total_life_cover_paise: int
    monthly_income_paise: int
    cash_balance_paise: int
    essential_monthly_expense_paise: int
    total_monthly_emi_paise: int


@dataclass(frozen=True)
class ComponentCeiling:
    name: str
    ceiling: int
    applicable: bool  # False for insurance-adequacy when dependents_count == 0


@dataclass(frozen=True)
class CapacityResult:
    rule_table_version: str
    ceiling: int  # min across applicable components
    components: tuple[ComponentCeiling, ...]


def _find_band(value: Decimal | float, bands: tuple[Band, ...]) -> Band:
    value = float(value)
    for band in bands:
        if value >= band.min_value and (band.max_value is None or value < band.max_value):
            return band
    raise ValueError(f"value {value} is not covered by any band in the rule table")


def compute_capacity_ceiling(
    inputs: CapacityInputs, rule_table: CapacityRuleTable = CAPACITY_RULE_TABLE_V1
) -> CapacityResult:
    buffer_band = _find_band(inputs.buffer_coverage_months, rule_table.buffer_months_bands)
    emi_band = _find_band(inputs.emi_to_income_ratio, rule_table.emi_to_income_bands)

    stability_ceiling = (
        rule_table.regular_income_ceiling
        if inputs.income_stability == IncomeStabilityValue.REGULAR
        else rule_table.irregular_income_ceiling
    )

    if inputs.dependents_count <= 0:
        insurance_ceiling = 5
        insurance_applicable = False
    else:
        required_cover = inputs.monthly_income_paise * 12 * rule_table.required_life_cover_income_multiple
        coverage_ratio = Decimal(inputs.total_life_cover_paise) / Decimal(required_cover) if required_cover > 0 else Decimal(0)
        insurance_band = _find_band(coverage_ratio, rule_table.insurance_coverage_bands)
        insurance_ceiling = insurance_band.ceiling
        insurance_applicable = True

    components = (
        ComponentCeiling("buffer_months", buffer_band.ceiling, True),
        ComponentCeiling("emi_to_income_ratio", emi_band.ceiling, True),
        ComponentCeiling("income_stability", stability_ceiling, True),
        ComponentCeiling("insurance_adequacy", insurance_ceiling, insurance_applicable),
    )
    applicable_ceilings = [c.ceiling for c in components if c.applicable]
    overall_ceiling = min(applicable_ceilings)

    return CapacityResult(rule_table_version=rule_table.version, ceiling=overall_ceiling, components=components)


# --- final tier + explanation ---


@dataclass(frozen=True)
class UnlockCondition:
    constraint: str
    message: str
    current_value: str
    target_value: str


@dataclass(frozen=True)
class FinalTierResult:
    stated_tier: int
    capacity_ceiling: int
    final_tier: int
    capped: bool
    binding_constraints: tuple[str, ...]
    unlock_conditions: tuple[UnlockCondition, ...]
    # Carried through from StatedTierResult.estimation_method, defaulted
    # the same way (see StatedTierResult).
    estimation_method: str = "deterministic"
    joint_unlock_plan: tuple[UnlockCondition, ...] = ()
    achievable_tier: int | None = None
    blocking_constraints: tuple[str, ...] = ()
    unlock_plan_version: str | None = None


def _indian_grouping(n: int) -> str:
    """Format an integer with Indian digit grouping: last 3 digits, then
    groups of 2 (e.g. 12000000 -> "1,20,00,000"), not the Western
    thousands grouping "12,000,000" — this is a rupee-figure display for
    Indian users."""
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) <= 3:
        return sign + digits

    last3, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return sign + ",".join(groups) + "," + last3


def _rupees(paise: int) -> str:
    return f"Rs {_indian_grouping(paise // 100)}"


def _target_ceiling_for(stated_tier: int) -> int:
    return min(stated_tier, 5)


def _rounded_rupees(paise: Decimal) -> int:
    return int((paise / Decimal(100)).to_integral_value(rounding=ROUND_CEILING))


def _assert_component_reaches(
    inputs: CapacityInputs,
    constraint: str,
    target_ceiling: int,
    rule_table: CapacityRuleTable,
) -> None:
    result = compute_capacity_ceiling(inputs, rule_table)
    component = next(component for component in result.components if component.name == constraint)
    assert component.ceiling >= target_ceiling, (
        f"{constraint} unlock action did not reach tier {target_ceiling}: "
        f"component ceiling is {component.ceiling}"
    )


def _unlock_buffer(
    target_ceiling: int, inputs: CapacityInputs, rule_table: CapacityRuleTable
) -> tuple[UnlockCondition, CapacityInputs]:
    target_band = next(b for b in rule_table.buffer_months_bands if b.ceiling == target_ceiling)
    required_months = Decimal(str(target_band.min_value))
    required_cash_paise = _rounded_rupees(
        required_months * Decimal(inputs.essential_monthly_expense_paise)
    ) * 100
    shortfall_paise = max(0, required_cash_paise - inputs.cash_balance_paise)
    increase_rupees = _rounded_rupees(Decimal(shortfall_paise))
    updated = replace(
        inputs,
        cash_balance_paise=inputs.cash_balance_paise + increase_rupees * 100,
        buffer_coverage_months=(
            Decimal(inputs.cash_balance_paise + increase_rupees * 100)
            / Decimal(inputs.essential_monthly_expense_paise)
        ),
    )
    _assert_component_reaches(updated, "buffer_months", target_ceiling, rule_table)
    return UnlockCondition(
        constraint="buffer_months",
        message=f"Reach {required_months} months of emergency buffer - you need Rs {_indian_grouping(increase_rupees)} more in cash savings.",
        current_value=f"{inputs.buffer_coverage_months} months",
        target_value=f"{required_months} months",
    ), updated


def _unlock_emi(
    target_ceiling: int, inputs: CapacityInputs, rule_table: CapacityRuleTable
) -> tuple[UnlockCondition, CapacityInputs]:
    target_band = next(b for b in rule_table.emi_to_income_bands if b.ceiling == target_ceiling)
    required_ratio = Decimal(str(target_band.max_value))
    required_reduction_rupees = max(
        0,
        _rounded_rupees(
            Decimal(inputs.total_monthly_emi_paise)
            - required_ratio * Decimal(inputs.monthly_income_paise)
        )
        + 1,
    )
    updated_emi_paise = max(0, inputs.total_monthly_emi_paise - required_reduction_rupees * 100)
    updated = replace(
        inputs,
        total_monthly_emi_paise=updated_emi_paise,
        emi_to_income_ratio=Decimal(updated_emi_paise) / Decimal(inputs.monthly_income_paise),
    )
    _assert_component_reaches(updated, "emi_to_income_ratio", target_ceiling, rule_table)
    return UnlockCondition(
        constraint="emi_to_income_ratio",
        message=(
            f"Bring your EMI-to-income ratio below {required_ratio * 100:.0f}% - "
            f"reduce your monthly EMI outflow by Rs {_indian_grouping(required_reduction_rupees)}."
        ),
        current_value=f"{inputs.emi_to_income_ratio * 100:.1f}%",
        target_value=f"below {required_ratio * 100:.0f}%",
    ), updated


def _unlock_stability() -> UnlockCondition:
    return UnlockCondition(
        constraint="income_stability",
        message=(
            "This cap is tied to income stability: it lifts once your income is regular "
            "(steady, predictable pay each month) rather than irregular. There is no "
            "partial credit for this constraint in the current rule table."
        ),
        current_value="irregular",
        target_value="regular",
    )


def _unlock_insurance(
    target_ceiling: int, inputs: CapacityInputs, rule_table: CapacityRuleTable
) -> tuple[UnlockCondition, CapacityInputs]:
    target_band = next(b for b in rule_table.insurance_coverage_bands if b.ceiling == target_ceiling)
    required_ratio = Decimal(str(target_band.min_value))
    required_cover_base = Decimal(inputs.monthly_income_paise * 12 * rule_table.required_life_cover_income_multiple)
    required_cover_paise = _rounded_rupees(required_ratio * required_cover_base) * 100
    shortfall_paise = max(0, required_cover_paise - inputs.total_life_cover_paise)
    increase_rupees = _rounded_rupees(Decimal(shortfall_paise))
    updated = replace(
        inputs,
        total_life_cover_paise=inputs.total_life_cover_paise + increase_rupees * 100,
    )
    _assert_component_reaches(updated, "insurance_adequacy", target_ceiling, rule_table)
    return UnlockCondition(
        constraint="insurance_adequacy",
        message=(f"Increase life insurance cover by Rs {_indian_grouping(increase_rupees)} to reach at least "
                 f"Rs {_indian_grouping(required_cover_paise // 100)} total sum assured for your "
                 f"{inputs.dependents_count} dependent(s)."),
        current_value=_rupees(inputs.total_life_cover_paise),
        target_value=f"at least Rs {_indian_grouping(required_cover_paise // 100)}",
    ), updated


_UNLOCK_BUILDERS = {
    "buffer_months": _unlock_buffer,
    "emi_to_income_ratio": _unlock_emi,
    "insurance_adequacy": _unlock_insurance,
}


def compute_final_tier(
    stated: StatedTierResult,
    capacity: CapacityResult,
    inputs: CapacityInputs,
    rule_table: CapacityRuleTable = CAPACITY_RULE_TABLE_V1,
) -> FinalTierResult:
    final_tier = min(stated.tier, capacity.ceiling)
    capped = final_tier < stated.tier

    if not capped:
        return FinalTierResult(
            stated_tier=stated.tier,
            capacity_ceiling=capacity.ceiling,
            final_tier=final_tier,
            capped=False,
            binding_constraints=(),
            unlock_conditions=(),
            estimation_method=stated.estimation_method,
            achievable_tier=final_tier,
            unlock_plan_version="joint-v1",
        )

    binding = tuple(
        c.name for c in capacity.components if c.applicable and c.ceiling == capacity.ceiling
    )
    target_ceiling = _target_ceiling_for(stated.tier)
    component_ceilings = {component.name: component for component in capacity.components}
    blocking_constraints = tuple(
        component.name
        for component in capacity.components
        if component.applicable
        and component.name not in _UNLOCK_BUILDERS
        and component.ceiling < target_ceiling
    )
    achievable_tier = min(
        target_ceiling,
        min(
            (
                component.ceiling
                for component in capacity.components
                if component.applicable and component.name not in _UNLOCK_BUILDERS
            ),
            default=target_ceiling,
        ),
    )

    def build_action(
        name: str, goal: int, base_inputs: CapacityInputs
    ) -> tuple[UnlockCondition, CapacityInputs]:
        if name == "income_stability":
            raise ValueError("income stability is not a user-changeable unlock action")
        return _UNLOCK_BUILDERS[name](goal, base_inputs, rule_table)

    unlock_conditions = []
    for name in binding:
        if name == "income_stability":
            unlock_conditions.append(_unlock_stability())
        elif component_ceilings[name].ceiling < achievable_tier:
            unlock_conditions.append(build_action(name, achievable_tier, inputs)[0])

    joint_unlock_plan = []
    joint_inputs = inputs
    for component in capacity.components:
        if (
            component.applicable
            and component.name in _UNLOCK_BUILDERS
            and component.ceiling < achievable_tier
        ):
            action, joint_inputs = build_action(component.name, achievable_tier, joint_inputs)
            joint_unlock_plan.append(action)

    joint_result = compute_capacity_ceiling(joint_inputs, rule_table)
    assert joint_result.ceiling >= achievable_tier, (
        f"joint unlock plan did not reach tier {achievable_tier}: "
        f"capacity ceiling is {joint_result.ceiling}"
    )

    return FinalTierResult(
        stated_tier=stated.tier,
        capacity_ceiling=capacity.ceiling,
        final_tier=final_tier,
        capped=True,
        binding_constraints=binding,
        unlock_conditions=tuple(unlock_conditions),
        estimation_method=stated.estimation_method,
        joint_unlock_plan=tuple(joint_unlock_plan),
        achievable_tier=achievable_tier,
        blocking_constraints=blocking_constraints,
        unlock_plan_version="joint-v1",
    )
