from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.suggestion_event import SuggestionEventRead
from app.schemas.user_monthly_snapshot import UserMonthlySnapshotRead
from app.services.event_log import get_user_event_history, get_user_snapshot_history

router = APIRouter()


@router.get("/users/{user_id}/events", response_model=list[SuggestionEventRead])
def read_user_events(
    user_id: str,
    module_source: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    return get_user_event_history(
        session,
        user_id,
        module_source=module_source,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}/snapshots", response_model=list[UserMonthlySnapshotRead])
def read_user_snapshots(
    user_id: str,
    since_month: date | None = None,
    until_month: date | None = None,
    limit: int = Query(24, ge=1, le=120),
    session: Session = Depends(get_session),
):
    return get_user_snapshot_history(
        session,
        user_id,
        since_month=since_month,
        until_month=until_month,
        limit=limit,
    )
