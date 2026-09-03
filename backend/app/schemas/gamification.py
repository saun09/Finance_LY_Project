from pydantic import BaseModel, ConfigDict


class AwardedMilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    milestone_id: str
    category: str
    headline: str
    details: dict


class MilestoneHistoryOut(BaseModel):
    milestones: list[AwardedMilestoneOut]
