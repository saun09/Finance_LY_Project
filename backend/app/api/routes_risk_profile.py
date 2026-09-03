from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.risk_profile import RiskProfileAnswersIn, RiskTierOut
from app.services.event_log import get_user_event_history
from app.services.onboarding import ProfileNotFoundError
from app.services.risk_profile_service import compute_and_log_risk_tier

router = APIRouter(prefix="/users/{user_id}/risk-profile", tags=["risk_profile"])


def _to_risk_tier_out(result) -> RiskTierOut:
    return RiskTierOut(
        stated_tier=result.stated_tier,
        capacity_ceiling=result.capacity_ceiling,
        final_tier=result.final_tier,
        capped=result.capped,
        binding_constraints=result.binding_constraints,
        unlock_conditions=[u.__dict__ for u in result.unlock_conditions],
    )


@router.post("", response_model=RiskTierOut)
def post_risk_profile(user_id: str, body: RiskProfileAnswersIn, session: Session = Depends(get_session)):
    try:
        result = compute_and_log_risk_tier(session, user_id, body.answers)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_risk_tier_out(result)


@router.get("/latest", response_model=RiskTierOut)
def get_latest_risk_profile(user_id: str, session: Session = Depends(get_session)):
    events = get_user_event_history(session, user_id, module_source="risk_profile", limit=1)
    if not events:
        raise HTTPException(status_code=404, detail=f"no risk_profile computation found for user_id={user_id!r}")
    v = events[0].suggested_value
    return RiskTierOut(
        stated_tier=v["stated_tier"],
        capacity_ceiling=v["capacity_ceiling"],
        final_tier=v["final_tier"],
        capped=v["capped"],
        binding_constraints=tuple(v["binding_constraints"]),
        unlock_conditions=v["unlock_conditions"],
    )
