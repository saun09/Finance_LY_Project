from decimal import Decimal

from pydantic import BaseModel

from app.services.asset_classification_config import AssetClass
from app.services.personalization import EditActionTaken


class RecordAllocationOutcomeIn(BaseModel):
    action_taken: EditActionTaken
    chosen_target_pct: dict[AssetClass, Decimal] | None = None
    funded: bool | None = None


class OffsetStepOut(BaseModel):
    step: int
    weight: Decimal
    delta_pct: Decimal
    offset_before: Decimal
    offset_after: Decimal


class PersonalizationOut(BaseModel):
    offset_pct_points: Decimal
    edits_considered: int
    final_tier: int
    capacity_ceiling: int
    base_target_pct: dict[AssetClass, Decimal]
    displayed_target_pct: dict[AssetClass, Decimal]
    trace: list[OffsetStepOut]
