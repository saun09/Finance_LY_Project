from pydantic import BaseModel


class RiskProfileAnswersIn(BaseModel):
    answers: dict[str, str]


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
