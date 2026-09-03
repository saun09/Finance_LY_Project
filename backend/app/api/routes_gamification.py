from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.gamification import AwardedMilestoneOut, MilestoneHistoryOut
from app.services.gamification_service import check_milestones, get_milestone_history
from app.services.onboarding import ProfileNotFoundError

router = APIRouter(prefix="/users/{user_id}/gamification", tags=["gamification"])


@router.post("/check", response_model=list[AwardedMilestoneOut])
def post_check_milestones(user_id: str, session: Session = Depends(get_session)):
    try:
        newly_awarded = check_milestones(session, user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return newly_awarded


@router.get("/history", response_model=MilestoneHistoryOut)
def get_history(user_id: str, session: Session = Depends(get_session)):
    return MilestoneHistoryOut(milestones=get_milestone_history(session, user_id))
