"""Module 4: pure asset-classification and portfolio-descriptive logic. No
I/O, no model calls — everything here is a deterministic function of a
holding's declared type and value, tested independently in
tests/test_asset_classification.py.

Look-through vs. wrapper-level, deliberately different:

- Asset-class exposure IS decomposed (look-through): a hybrid fund's
  equity slice counts as equity exposure in the aggregate, not as one
  lump under its wrapper label.
- Liquidity and tax treatment are NOT decomposed: they're properties of
  the whole instrument (you can't partially withdraw just the equity
  portion of a locked ULIP before its lock-in ends), so they're aggregated
  at the holding level, not split by asset-class slice.

Per the project's hard legal boundary, nothing in this module ever
receives or emits a named fund/stock/scheme — only `HoldingType` category
values and computed numbers.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.services.asset_classification_config import (
    HOLDING_TYPE_PROFILES_V1,
    AssetClass,
    HoldingType,
    HoldingTypeProfile,
    Liquidity,
)


@dataclass(frozen=True)
class HoldingClassification:
    holding_id: str
    holding_type: HoldingType
    value_paise: int
    decomposition_paise: dict[AssetClass, int]  # look-through exposure, sums to value_paise
    liquidity: Liquidity
    lock_in_months: int | None
    tax_treatment_category: str
    is_look_through: bool
    decomposition_notes: str | None


def _split_paise(value_paise: int, fractions: dict[AssetClass, Decimal]) -> dict[AssetClass, int]:
    """Split an integer paise amount across asset classes by fraction,
    rounding each share to the nearest paise, with any residual from
    rounding assigned to the largest share so the parts always sum back to
    the whole (no money silently created or lost to rounding)."""
    raw = {ac: (Decimal(value_paise) * frac) for ac, frac in fractions.items()}
    rounded = {ac: int(amt.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for ac, amt in raw.items()}

    residual = value_paise - sum(rounded.values())
    if residual != 0:
        largest_class = max(fractions, key=lambda ac: fractions[ac])
        rounded[largest_class] += residual

    return rounded


def classify_holding(
    holding_id: str,
    holding_type: HoldingType,
    value_paise: int,
    profiles: dict[HoldingType, HoldingTypeProfile] = HOLDING_TYPE_PROFILES_V1,
) -> HoldingClassification:
    if holding_type not in profiles:
        raise ValueError(f"unknown holding_type {holding_type!r}; not in the classification config")

    profile = profiles[holding_type]
    decomposition_paise = _split_paise(value_paise, profile.decomposition)

    return HoldingClassification(
        holding_id=holding_id,
        holding_type=holding_type,
        value_paise=value_paise,
        decomposition_paise=decomposition_paise,
        liquidity=profile.liquidity,
        lock_in_months=profile.lock_in_months,
        tax_treatment_category=profile.tax_treatment_category,
        is_look_through=profile.is_look_through,
        decomposition_notes=profile.decomposition_notes,
    )


@dataclass(frozen=True)
class ConcentrationMetrics:
    largest_holding_pct: Decimal  # largest single holding, % of total portfolio value
    largest_holding_id: str | None
    asset_class_hhi_bps: int  # Herfindahl-Hirschman Index over asset-class weights, 0-10000


@dataclass(frozen=True)
class PortfolioClassification:
    total_value_paise: int
    holdings: tuple[HoldingClassification, ...]
    exposure_by_asset_class_paise: dict[AssetClass, int]  # look-through, sums to total_value_paise
    exposure_by_asset_class_pct: dict[AssetClass, Decimal]  # sums to 100 (within rounding)
    concentration: ConcentrationMetrics
    liquidity_breakdown_paise: dict[Liquidity, int]  # wrapper-level, NOT decomposed
    tax_treatment_breakdown_paise: dict[str, int]  # wrapper-level, NOT decomposed


def _pct(part: int, whole: int) -> Decimal:
    if whole <= 0:
        return Decimal("0.00")
    return (Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def aggregate_classifications(classifications: list[HoldingClassification]) -> PortfolioClassification:
    total_value_paise = sum(c.value_paise for c in classifications)

    exposure_paise: dict[AssetClass, int] = {ac: 0 for ac in AssetClass}
    liquidity_paise: dict[Liquidity, int] = {liq: 0 for liq in Liquidity}
    tax_paise: dict[str, int] = {}

    for c in classifications:
        for ac, paise in c.decomposition_paise.items():
            exposure_paise[ac] += paise
        liquidity_paise[c.liquidity] += c.value_paise
        tax_paise[c.tax_treatment_category] = tax_paise.get(c.tax_treatment_category, 0) + c.value_paise

    exposure_pct = {ac: _pct(paise, total_value_paise) for ac, paise in exposure_paise.items()}

    if classifications:
        largest = max(classifications, key=lambda c: c.value_paise)
        largest_holding_pct = _pct(largest.value_paise, total_value_paise)
        largest_holding_id = largest.holding_id
    else:
        largest_holding_pct = Decimal("0.00")
        largest_holding_id = None

    hhi_bps = 0
    if total_value_paise > 0:
        for ac, paise in exposure_paise.items():
            share_bps = Decimal(paise) * 10_000 / Decimal(total_value_paise)  # basis points, e.g. 2500 = 25%
            hhi_bps += int((share_bps * share_bps / 10_000).to_integral_value(rounding=ROUND_HALF_UP))

    return PortfolioClassification(
        total_value_paise=total_value_paise,
        holdings=tuple(classifications),
        exposure_by_asset_class_paise=exposure_paise,
        exposure_by_asset_class_pct=exposure_pct,
        concentration=ConcentrationMetrics(
            largest_holding_pct=largest_holding_pct,
            largest_holding_id=largest_holding_id,
            asset_class_hhi_bps=hhi_bps,
        ),
        liquidity_breakdown_paise=liquidity_paise,
        tax_treatment_breakdown_paise=tax_paise,
    )
