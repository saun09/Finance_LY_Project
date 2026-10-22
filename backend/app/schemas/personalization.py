from decimal import Decimal

from pydantic import BaseModel

from app.services.asset_classification_config import AssetClass
from app.services.personalization import EditActionTaken


class RecordAllocationOutcomeIn(BaseModel):
    action_taken: EditActionTaken
    # required for "edited"; ignored for "accepted" (the displayed mix is
    # recorded server-side) and for "rejected"/"ignored"
    chosen_target_pct: dict[AssetClass, Decimal] | None = None
    funded: bool | None = None
    # required for "rejected": one of personalization.REJECT_REASON_CODES
    reason_code: str | None = None


class MarkFundedIn(BaseModel):
    funded: bool = True


class OffsetStepOut(BaseModel):
    step: int
    weight: Decimal
    delta_pct: Decimal
    offset_before: Decimal
    offset_after: Decimal
    action_taken: EditActionTaken | None = None
    funded: bool | None = None
    reason_code: str | None = None


class PersonalizationOut(BaseModel):
    offset_pct_points: Decimal
    applied_offset_pct_points: Decimal
    offset_capped: bool
    cap_reason: str | None
    max_equity_pct: Decimal
    capacity_binding_constraints: list[str]
    edits_considered: int
    final_tier: int
    capacity_ceiling: int
    base_target_pct: dict[AssetClass, Decimal]
    displayed_target_pct: dict[AssetClass, Decimal]
    trace: list[OffsetStepOut]
