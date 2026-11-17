"""Async runs of the n8n rumour workflow. See models/rumour_verification_job.py
for why this can't be a single blocking request."""

import hashlib
import hmac
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import PUBLIC_BASE_URL
from app.models.rumour_verification_job import JOB_COMPLETED, JOB_FAILED, JOB_PENDING, RumourVerificationJob
from app.services.rumour_verification_bridge import (
    N8N_ENGINE_NAME,
    log_verification_event,
    parse_n8n_result,
    start_verification,
    verification_result_to_suggested_value,
)
from app.services.transparency import THIRD_PARTY_OUTPUT_LABEL

#: A pending job with no callback after this long is reported as failed --
#: the workflow errored or never reached its callback node, and the client
#: shouldn't poll forever.
JOB_EXPIRY = timedelta(minutes=10)


class JobNotFoundError(LookupError):
    pass


class CallbackRejectedError(PermissionError):
    pass


class PublicUrlNotConfiguredError(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    # SQLite hands timezone-aware columns back naive; they were stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def callback_url_for(job_id: str) -> str:
    return f"{PUBLIC_BASE_URL}/rumour-verification/jobs/{job_id}/result"


def create_and_start_job(
    session: Session,
    *,
    user_id: str,
    rumour_text: str,
    rumour_date: date | None = None,
    company_name: str | None = None,
    evaluated_at: datetime | None = None,
    log_event: bool = True,
) -> RumourVerificationJob:
    """Record a pending job and hand the rumour to n8n. Raises
    PublicUrlNotConfiguredError when n8n would have nowhere to report back,
    or RuntimeError if n8n can't be reached (the job is then marked failed)."""
    if not PUBLIC_BASE_URL:
        raise PublicUrlNotConfiguredError(
            "The broader workflow reports its result back to this server, so it needs a public URL. "
            "It works on the deployed app; locally, use Exchange Filings mode."
        )

    token = secrets.token_urlsafe(32)
    job = RumourVerificationJob(
        user_id=user_id,
        status=JOB_PENDING,
        rumour_text=rumour_text,
        rumour_date=rumour_date,
        company_name=company_name,
        log_event=log_event,
        callback_token_hash=_hash_token(token),
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        start_verification(
            rumour_text,
            job_id=job.id,
            callback_url=callback_url_for(job.id),
            callback_token=token,
            rumour_date=rumour_date,
            company_name=company_name,
            evaluated_at=evaluated_at,
        )
    except RuntimeError as exc:
        _finish(session, job, status=JOB_FAILED, error=str(exc))
        raise
    return job


def get_job(session: Session, *, user_id: str, job_id: str) -> RumourVerificationJob:
    job = session.get(RumourVerificationJob, job_id)
    if job is None or job.user_id != user_id:
        raise JobNotFoundError(f"no rumour verification job id={job_id!r} for user_id={user_id!r}")
    if job.status == JOB_PENDING and _utcnow() - _as_utc(job.created_at) > JOB_EXPIRY:
        _finish(
            session,
            job,
            status=JOB_FAILED,
            error=f"The broader workflow didn't report back within {int(JOB_EXPIRY.total_seconds() // 60)} minutes. Try again.",
        )
    return job


def complete_job_from_callback(session: Session, *, job_id: str, token: str | None, data: Any) -> RumourVerificationJob:
    """Store n8n's result. The token must match the one sent with this job.
    A body with an `error` and no `verdict` marks the job failed, so an n8n
    error branch can report failures instead of leaving the job to expire."""
    job = session.get(RumourVerificationJob, job_id)
    # Same answer for "no such job" and "wrong token", so the endpoint can't
    # be used to probe which job ids exist.
    if job is None or not token or not hmac.compare_digest(job.callback_token_hash, _hash_token(token)):
        raise CallbackRejectedError("invalid job id or callback token")
    if job.status != JOB_PENDING:
        return job  # n8n retried a delivery we already stored

    if isinstance(data, list) and len(data) == 1:
        data = data[0]  # n8n can wrap a single item in a list
    if isinstance(data, dict) and data.get("error") and not data.get("verdict"):
        _finish(session, job, status=JOB_FAILED, error=f"The broader workflow failed: {str(data['error'])[:300]}")
        return job

    try:
        result = parse_n8n_result(
            data, rumour_text=job.rumour_text, rumour_date=job.rumour_date, company_name=job.company_name
        )
    except RuntimeError as exc:
        _finish(session, job, status=JOB_FAILED, error=str(exc))
        return job

    suggested_value = verification_result_to_suggested_value(result)
    logged_event_id = None
    if job.log_event:
        logged_event_id = log_verification_event(session, job.user_id, result).event_id

    payload = {
        "query_text": result.query_text,
        "rumour_date": result.rumour_date.isoformat() if result.rumour_date else None,
        "status": suggested_value["status"],
        "matched_score": suggested_value["matched_score"],
        "matched_filing": suggested_value["matched_filing"],
        "candidates_considered": suggested_value["candidates_considered"],
        "candidates_passing": suggested_value["candidates_passing"],
        "top_candidate_reasons": suggested_value["top_candidate_reasons"],
        "logged_event_id": logged_event_id,
        "engine": N8N_ENGINE_NAME,
        "framing_label": THIRD_PARTY_OUTPUT_LABEL,
    }
    _finish(session, job, status=JOB_COMPLETED, result=payload)
    return job


def _finish(
    session: Session,
    job: RumourVerificationJob,
    *,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    job.status = status
    job.result = result
    job.error = error
    job.completed_at = _utcnow()
    session.commit()
    session.refresh(job)
