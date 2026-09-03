from pydantic import BaseModel, ConfigDict


class AwardedMilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    milestone_id: str
    category: str
    headline: str
    details: dict


class MilestoneHistoryOut(BaseModel):
    milestones: list[AwardedMilestoneOut]


class QuizQuestionOut(BaseModel):
    question_id: str
    prompt: str
    options: list[str]
    passed: bool = False


class RoadmapTopicOut(BaseModel):
    topic_id: str
    title: str
    description: str
    completed: bool = False
    quiz_question: QuizQuestionOut | None = None


class RoadmapLevelOut(BaseModel):
    level: int
    title: str
    topics: list[RoadmapTopicOut]


class ChecklistItemOut(BaseModel):
    item_id: str
    title: str
    section: str
    completed: bool = False


class EducationCompletionIn(BaseModel):
    item_id: str
    kind: str
    correct: bool | None = None
    answer_index: int | None = None


class QuizResultOut(BaseModel):
    correct: bool
    explanation: str


class BadgeOut(BaseModel):
    badge_id: str
    title: str
    description: str
    earned: bool


class EducationProgressOut(BaseModel):
    roadmap: list[RoadmapLevelOut]
    checklist: list[ChecklistItemOut]
    badges: list[BadgeOut]
    completed_topics: int
    total_topics: int
    progress_pct: int
    learning_streak_days: int
