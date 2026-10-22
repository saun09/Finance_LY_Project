from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.risk_profile import QuestionnaireOut, RiskProfileAnswersIn, RiskTierOut
from app.services.event_log import get_user_event_history
from app.services.onboarding import ProfileNotFoundError
from app.services.risk_profile_config import QUESTIONNAIRE_V2
from app.services.risk_profile_ml import FEATURE_ORDER_REDUCED, MLModelUnavailableError
from app.services.risk_profile_service import compute_and_log_risk_tier

router = APIRouter(prefix="/users/{user_id}/risk-profile", tags=["risk_profile"])

# Not user-scoped -- the questionnaire is static config, not per-user data.
# Exists purely so a frontend never has to hardcode a duplicate copy of
# QUESTIONNAIRE_V1 (which would drift out of sync if the config version
# ever changes). Deliberately omits each option's point value: the
# frontend only needs `value` (to submit back) and `label` (to display) --
# it must never compute the score itself, since Module 3's weighted sum is
# the sole source of truth for a user's stated tier.
config_router = APIRouter(prefix="/risk-profile", tags=["risk_profile"])


@config_router.get("/questionnaire", response_model=QuestionnaireOut)
def get_questionnaire():
    return QuestionnaireOut(
        version=QUESTIONNAIRE_V2.version,
        effective_date=QUESTIONNAIRE_V2.effective_date,
        questions=[
            {
                "id": q.id,
                "text": q.text,
                "weight": q.weight,
                "options": [{"value": o.value, "label": o.label} for o in q.options],
            }
            for q in QUESTIONNAIRE_V2.questions
        ],
        required_question_ids=list(FEATURE_ORDER_REDUCED),
    )


def _to_risk_tier_out(result) -> RiskTierOut:
    return RiskTierOut(
        stated_tier=result.stated_tier,
        capacity_ceiling=result.capacity_ceiling,
        final_tier=result.final_tier,
        capped=result.capped,
        binding_constraints=result.binding_constraints,
        unlock_conditions=[u.__dict__ for u in result.unlock_conditions],
        estimation_method=result.estimation_method,
    )


@router.post("", response_model=RiskTierOut)
def post_risk_profile(user_id: str, body: RiskProfileAnswersIn, session: Session = Depends(get_session)):
    try:
        result = compute_and_log_risk_tier(session, user_id, body.answers)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MLModelUnavailableError as exc:
        # Only reachable from quick mode (4 answers): there is no
        # deterministic fallback when the reduced model can't load, unlike
        # a full-7 submission where a missing model just skips a bonus
        # explanation. 503, not 422 -- the answers themselves are valid.
        raise HTTPException(
            status_code=503,
            detail="Quick-mode scoring is unavailable right now. Please answer the remaining 3 questions, or try again shortly.",
        ) from exc
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
        estimation_method=v.get("estimation_method", "deterministic"),
    )
