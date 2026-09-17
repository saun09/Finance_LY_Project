from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.transparency import (
    AvailableDecisionTypesOut,
    ContestDecisionIn,
    DecisionEventSummaryOut,
    TraceComparisonOut,
    TraceResultOut,
)
from app.services.transparency import (
    CONTEST_REASON_CODES,
    InvalidContestReasonError,
    NoSuchDecisionEventError,
    UnknownDecisionTypeError,
    compare_traces,
    contest_decision,
    get_trace,
    list_available_decision_types,
    list_decision_events,
)

router = APIRouter(prefix="/users/{user_id}/transparency", tags=["transparency"])


@router.get("", response_model=AvailableDecisionTypesOut)
def get_available_decision_types(user_id: str, session: Session = Depends(get_session)):
    return AvailableDecisionTypesOut(counts_by_module_source=list_available_decision_types(session, user_id))


@router.get("/contest-reasons", response_model=list[str])
def get_contest_reason_codes():
    """The closed set of reasons a user may attach when disputing a trace.
    Served rather than hardcoded client-side so the two can't drift."""
    return list(CONTEST_REASON_CODES)


@router.get("/{module_source}", response_model=TraceResultOut)
def get_decision_trace(
    user_id: str,
    module_source: str,
    event_id: str | None = None,
    session: Session = Depends(get_session),
):
    try:
        trace = get_trace(session, user_id, module_source, event_id)
    except UnknownDecisionTypeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoSuchDecisionEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return trace


@router.get("/{module_source}/history", response_model=list[DecisionEventSummaryOut])
def get_decision_history(
    user_id: str,
    module_source: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """Every recorded decision of this type, newest first. Module 1 already
    stores them all; this is what lets a user ask "my tier changed -- when,
    and what moved?" instead of only ever seeing the current one."""
    try:
        return list_decision_events(session, user_id, module_source, limit=limit, offset=offset)
    except UnknownDecisionTypeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{module_source}/compare", response_model=TraceComparisonOut)
def get_trace_comparison(
    user_id: str,
    module_source: str,
    before_event_id: str = Query(...),
    after_event_id: str = Query(...),
    session: Session = Depends(get_session),
):
    """Field-level diff between two decisions of the same type -- which
    stored input actually moved between them."""
    try:
        return compare_traces(session, user_id, module_source, before_event_id, after_event_id)
    except UnknownDecisionTypeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoSuchDecisionEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{module_source}/contest", response_model=TraceResultOut)
def post_contest_decision(
    user_id: str,
    module_source: str,
    body: ContestDecisionIn,
    session: Session = Depends(get_session),
):
    """Record that the user disputes this decision, through Module 1's
    existing outcome fields so the objection reaches Module 7's feedback
    loop rather than stopping at a read-only screen."""
    try:
        return contest_decision(
            session, user_id, module_source, body.event_id, body.reason_code, note=body.note
        )
    except UnknownDecisionTypeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoSuchDecisionEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidContestReasonError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
