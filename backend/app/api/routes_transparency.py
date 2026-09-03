from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.transparency import AvailableDecisionTypesOut, TraceResultOut
from app.services.transparency import (
    NoSuchDecisionEventError,
    UnknownDecisionTypeError,
    get_trace,
    list_available_decision_types,
)

router = APIRouter(prefix="/users/{user_id}/transparency", tags=["transparency"])


@router.get("", response_model=AvailableDecisionTypesOut)
def get_available_decision_types(user_id: str, session: Session = Depends(get_session)):
    return AvailableDecisionTypesOut(counts_by_module_source=list_available_decision_types(session, user_id))


@router.get("/{module_source}", response_model=TraceResultOut)
def get_decision_trace(user_id: str, module_source: str, event_id: str | None = None, session: Session = Depends(get_session)):
    try:
        trace = get_trace(session, user_id, module_source, event_id)
    except UnknownDecisionTypeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoSuchDecisionEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return trace
