from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.rumour_verification import (
    LocalRumourVerificationOut,
    RumourVerificationIn,
    RumourVerificationOut,
)
from app.services.rumour_local_engine import (
    ENGINE_NAME as LOCAL_ENGINE_NAME,
    LocalEngineUnavailableError,
    local_engine_available,
    log_local_verification_event,
    run_local_verification,
    verification_result_to_suggested_value as local_result_to_suggested_value,
)
from app.services.rumour_verification_bridge import (
    N8N_ENGINE_NAME,
    log_verification_event,
    run_verification,
    verification_result_to_suggested_value,
)
from app.services.transparency import (
    LOCAL_ENGINE_CLAIM_NOTE,
    RETRIEVAL_EXPLANATION_LABEL,
    THIRD_PARTY_OUTPUT_LABEL,
)

router = APIRouter(prefix="/users/{user_id}/rumour-verification", tags=["rumour_verification"])


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


@router.post("", response_model=RumourVerificationOut)
def post_verify_rumour(
    user_id: str,
    body: RumourVerificationIn,
    log_event: bool = Query(True, description="Log this verification as an auditable suggestion_event"),
    session: Session = Depends(get_session),
):
    """Calls the n8n Module 5 workflow (see rumour_verification_bridge.py)
    and, by default, logs the result as a suggestion_event purely for
    auditability -- never touching action_taken/chosen_value/funded, since
    a verification result isn't something a user accepts/edits/rejects the
    way a suggestion is.

    The response carries `engine` and `framing_label` so the client cannot
    present this workflow's self-reported prose as the project's
    explainability claim; for that, use `/explain` below.
    """
    try:
        result = run_verification(
            body.rumour_text, rumour_date=body.rumour_date, company_name=body.company_name, evaluated_at=body.evaluated_at,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    suggested_value = verification_result_to_suggested_value(result)

    logged_event_id = None
    if log_event:
        event = log_verification_event(session, user_id, result)
        logged_event_id = event.event_id

    return RumourVerificationOut(
        query_text=result.query_text,
        rumour_date=result.rumour_date,
        status=suggested_value["status"],
        matched_score=suggested_value["matched_score"],
        matched_filing=suggested_value["matched_filing"],
        candidates_considered=suggested_value["candidates_considered"],
        candidates_passing=suggested_value["candidates_passing"],
        top_candidate_reasons=suggested_value["top_candidate_reasons"],
        logged_event_id=logged_event_id,
        engine=N8N_ENGINE_NAME,
        framing_label=THIRD_PARTY_OUTPUT_LABEL,
    )


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
