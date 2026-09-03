from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.rumour_verification import RumourVerificationIn, RumourVerificationOut
from app.services.rumour_verification_bridge import (
    log_verification_event,
    run_verification,
    verification_result_to_suggested_value,
)

router = APIRouter(prefix="/users/{user_id}/rumour-verification", tags=["rumour_verification"])


@router.post("", response_model=RumourVerificationOut)
def post_verify_rumour(
    user_id: str,
    body: RumourVerificationIn,
    log_event: bool = Query(True, description="Log this verification as an auditable suggestion_event"),
    session: Session = Depends(get_session),
):
    """Calls Module 5's own verify_rumour unchanged (see
    rumour_verification_bridge.py) and, by default, logs the result as a
    suggestion_event purely for auditability -- never touching
    action_taken/chosen_value/funded, since a verification result isn't
    something a user accepts/edits/rejects the way a suggestion is."""
    result = run_verification(
        body.rumour_text, rumour_date=body.rumour_date, company_name=body.company_name, evaluated_at=body.evaluated_at,
    )
    suggested_value = verification_result_to_suggested_value(result)

    logged_event_id = None
    if log_event:
        event = log_verification_event(session, user_id, result)
        logged_event_id = event.event_id

    return RumourVerificationOut(
        query_text=result.query_text,
        rumour_date=result.rumour_date,
        status=result.status,
        matched_score=result.matched_score,
        matched_filing=suggested_value["matched_filing"],
        candidates_considered=suggested_value["candidates_considered"],
        candidates_passing=suggested_value["candidates_passing"],
        top_candidate_reasons=suggested_value["top_candidate_reasons"],
        logged_event_id=logged_event_id,
    )
