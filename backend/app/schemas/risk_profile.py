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
