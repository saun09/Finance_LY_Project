from decimal import Decimal

from pydantic import BaseModel

from app.services.asset_classification_config import AssetClass, Liquidity


class ConcentrationOut(BaseModel):
    largest_holding_pct: Decimal
    largest_holding_id: str | None
    asset_class_hhi_bps: int


class HoldingClassificationOut(BaseModel):
    holding_id: str
    holding_type: str
    value_paise: int
    decomposition_paise: dict[AssetClass, int]
    liquidity: Liquidity
    lock_in_months: int | None
    tax_treatment_category: str
    is_look_through: bool


class AllocationPersonalizationOut(BaseModel):
    """Module 7's effect on this allocation. `offset_pct_points` is what
    actually reached the displayed mix; `requested_offset_pct_points` is
    what the user's history asked for before the capacity cap."""

    offset_pct_points: Decimal
    requested_offset_pct_points: Decimal
    capped: bool
    cap_reason: str | None
    max_equity_pct: Decimal
    capacity_ceiling: int
    capacity_binding_constraints: list[str]
    edits_considered: int


class AllocationReportOut(BaseModel):
    # record the user's response to this report against this id
    event_id: str
    final_tier: int
    rule_table_version: str
    reasoning: str
    # the tier's base target, straight from the rule table
    target_pct: dict[AssetClass, Decimal]
    # base + personal offset, capped by capacity -- what the user is shown
    displayed_target_pct: dict[AssetClass, Decimal]
    personalization: AllocationPersonalizationOut
    current_exposure_pct: dict[AssetClass, Decimal]
    current_exposure_paise: dict[AssetClass, int]
    total_value_paise: int
    concentration: ConcentrationOut
    liquidity_breakdown_paise: dict[Liquidity, int]
    tax_treatment_breakdown_paise: dict[str, int]
    holdings: list[HoldingClassificationOut]
