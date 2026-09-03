from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.personalization import PersonalizationOut, RecordAllocationOutcomeIn
from app.services.personalization_service import (
    AllocationEventNotFoundError,
    NoAllocationSuggestionError,
    NoRiskTierError,
    compute_and_log_personalization,
    record_allocation_outcome,
)

router = APIRouter(prefix="/users/{user_id}", tags=["personalization"])


@router.post("/allocation/{event_id}/outcome")
def post_allocation_outcome(user_id: str, event_id: str, body: RecordAllocationOutcomeIn, session: Session = Depends(get_session)):
    try:
        record_allocation_outcome(
            session, user_id, event_id,
            action_taken=body.action_taken,
            chosen_target_pct=None if body.chosen_target_pct is None else {k.value: v for k, v in body.chosen_target_pct.items()},
            funded=body.funded,
        )
    except AllocationEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "recorded"}


@router.get("/personalization", response_model=PersonalizationOut)
def get_personalization(user_id: str, session: Session = Depends(get_session)):
    try:
        result = compute_and_log_personalization(session, user_id)
    except (NoAllocationSuggestionError, NoRiskTierError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return PersonalizationOut(
        offset_pct_points=result.offset_pct_points,
        edits_considered=result.edits_considered,
        final_tier=result.final_tier,
        capacity_ceiling=result.capacity_ceiling,
        base_target_pct=result.base_target_pct,
        displayed_target_pct=result.displayed_target_pct,
        trace=[s.__dict__ for s in result.trace],
    )
