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


class AllocationReportOut(BaseModel):
    final_tier: int
    rule_table_version: str
    reasoning: str
    target_pct: dict[AssetClass, Decimal]
    current_exposure_pct: dict[AssetClass, Decimal]
    current_exposure_paise: dict[AssetClass, int]
    total_value_paise: int
    concentration: ConcentrationOut
    liquidity_breakdown_paise: dict[Liquidity, int]
    tax_treatment_breakdown_paise: dict[str, int]
    holdings: list[HoldingClassificationOut]
