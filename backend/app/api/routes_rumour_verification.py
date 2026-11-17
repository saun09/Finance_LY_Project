from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.rumour_verification import (
    LocalRumourVerificationOut,
    RumourVerificationIn,
    RumourVerificationJobOut,
)
from app.services.rumour_local_engine import (
    ENGINE_NAME as LOCAL_ENGINE_NAME,
    LocalEngineUnavailableError,
    local_engine_available,
    log_local_verification_event,
    run_local_verification,
    verification_result_to_suggested_value as local_result_to_suggested_value,
)
from app.services.rumour_verification_bridge import N8N_ENGINE_NAME, N8NTimeoutError
from app.services.rumour_verification_jobs import (
    CallbackRejectedError,
    JobNotFoundError,
    PublicUrlNotConfiguredError,
    complete_job_from_callback,
    create_and_start_job,
    get_job,
)
from app.services.transparency import (
    LOCAL_ENGINE_CLAIM_NOTE,
    RETRIEVAL_EXPLANATION_LABEL,
    THIRD_PARTY_OUTPUT_LABEL,
)

router = APIRouter(prefix="/users/{user_id}/rumour-verification", tags=["rumour_verification"])
# n8n's callback has no user in its path -- the per-job token identifies it.
callback_router = APIRouter(prefix="/rumour-verification", tags=["rumour_verification"])


def _job_out(job) -> RumourVerificationJobOut:
    return RumourVerificationJobOut(job_id=job.id, status=job.status, result=job.result, error=job.error)


@router.get("/engines", response_model=dict)
def get_available_engines():
    """Which Module 5 engines this deployment can run, and what each one can
    honestly claim. The client shows this rather than assuming: only the
    local engine produces a constraint-elimination trace, and it is absent
    if its research dependencies aren't installed."""
    return {
        "engines": [
            {
                "engine": N8N_ENGINE_NAME,
                "available": True,
                "framing_label": THIRD_PARTY_OUTPUT_LABEL,
                "explains_eliminated_candidates": False,
                "description": (
                    "External LLM workflow. Not limited to a fixed corpus, but returns a "
                    "verdict and its own prose rationale -- no candidate list, so no "
                    "elimination trace this project can verify."
                ),
            },
            {
                "engine": LOCAL_ENGINE_NAME,
                "available": local_engine_available(),
                "framing_label": RETRIEVAL_EXPLANATION_LABEL,
                "explains_eliminated_candidates": True,
                "description": LOCAL_ENGINE_CLAIM_NOTE,
            },
        ]
    }


@router.post("", response_model=RumourVerificationJobOut, status_code=202)
def post_verify_rumour(
    user_id: str,
    body: RumourVerificationIn,
    log_event: bool = Query(True, description="Log this verification as an auditable suggestion_event"),
    session: Session = Depends(get_session),
):
    """Start the n8n Module 5 workflow and return a job to poll.

    The workflow takes minutes and n8n Cloud cuts requests at ~100s, so the
    verdict can't come back on this request: n8n POSTs it to the callback
    below, and GET /jobs/{job_id} reports it. Once complete, the result is
    (by default) logged as a suggestion_event purely for auditability.

    The result carries `engine` and `framing_label` so the client cannot
    present this workflow's self-reported prose as the project's
    explainability claim; for that, use `/explain` below.
    """
    try:
        job = create_and_start_job(
            session,
            user_id=user_id,
            rumour_text=body.rumour_text,
            rumour_date=body.rumour_date,
            company_name=body.company_name,
            evaluated_at=body.evaluated_at,
            log_event=log_event,
        )
    except PublicUrlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except N8NTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=RumourVerificationJobOut)
def get_verify_rumour_job(user_id: str, job_id: str, session: Session = Depends(get_session)):
    try:
        return _job_out(get_job(session, user_id=user_id, job_id=job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@callback_router.post("/jobs/{job_id}/result")
def post_verify_rumour_result(
    job_id: str,
    data: dict | list = Body(...),
    x_callback_token: str | None = Header(None),
    session: Session = Depends(get_session),
):
    """Called by the n8n workflow's last node with its final JSON (or
    `{"error": "..."}` from an error branch), plus the job's token in the
    X-Callback-Token header."""
    try:
        job = complete_job_from_callback(session, job_id=job_id, token=x_callback_token, data=data)
    except CallbackRejectedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"ok": True, "status": job.status}


@router.post("/explain", response_model=LocalRumourVerificationOut)
def post_explain_rumour(
    user_id: str,
    body: RumourVerificationIn,
    log_event: bool = Query(True, description="Log this verification as an auditable suggestion_event"),
    session: Session = Depends(get_session),
):
    """Run Module 5's local constrained-retrieval engine and return the full
    per-candidate elimination trace.

    This is the endpoint the project's explainability claim attaches to:
    every candidate considered, which of the three constraints eliminated
    each one that failed, and why the returned filing ranked first among
    those that survived. Restricted to the local filings corpus, which is
    exactly the trade for being able to show the working.
    """
    try:
        result = run_local_verification(
            body.rumour_text,
            rumour_date=body.rumour_date,
            company_name=body.company_name,
            evaluated_at=body.evaluated_at,
        )
    except LocalEngineUnavailableError as exc:
        # 503, not a silent fallback to the n8n path: a user who asked for
        # the explanation must not be handed something else that looks like
        # one.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    suggested_value = local_result_to_suggested_value(result)

    logged_event_id = None
    if log_event:
        event = log_local_verification_event(session, user_id, result)
        logged_event_id = event.event_id

    return LocalRumourVerificationOut(
        **{
            k: suggested_value[k]
            for k in (
                "query_text", "rumour_date", "status", "matched_score", "matched_filing",
                "candidates_considered", "candidates_passing", "candidates_eliminated",
                "eliminated_by_constraint", "why_ranked_first", "candidate_explanations",
                "full_trace_text",
            )
        },
        logged_event_id=logged_event_id,
        engine=LOCAL_ENGINE_NAME,
        framing_label=RETRIEVAL_EXPLANATION_LABEL,
        claim_note=LOCAL_ENGINE_CLAIM_NOTE,
    )
