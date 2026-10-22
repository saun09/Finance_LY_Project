from pydantic import BaseModel


class RiskProfileAnswersIn(BaseModel):
    answers: dict[str, str]


class QuestionOptionOut(BaseModel):
    value: str
    label: str


class QuestionOut(BaseModel):
    id: str
    text: str
    weight: int
    options: list[QuestionOptionOut]


class QuestionnaireOut(BaseModel):
    version: str
    effective_date: str
    questions: list[QuestionOut]
    # The 4 questions a quick-mode submission must still answer -- the
    # other 3 are optional. Sourced from risk_profile_ml.FEATURE_ORDER_REDUCED
    # so the frontend never hardcodes a copy that could drift out of sync.
    required_question_ids: list[str]


class UnlockConditionOut(BaseModel):
    constraint: str
    message: str
    current_value: str
    target_value: str


class RiskTierOut(BaseModel):
    stated_tier: int
    capacity_ceiling: int
    final_tier: int
    capped: bool
    binding_constraints: tuple[str, ...]
    unlock_conditions: tuple[UnlockConditionOut, ...]
    # "deterministic" for a full-7-answer submission; a model version
    # string when stated_tier instead came from the quick-mode (4-answer)
    # ML estimate. Defaulted for old event-log rows recorded before this
    # field existed.
    estimation_method: str = "deterministic"
