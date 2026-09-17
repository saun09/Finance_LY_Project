from datetime import date, datetime

from pydantic import BaseModel


class RumourVerificationIn(BaseModel):
    rumour_text: str
    rumour_date: date | None = None
    company_name: str | None = None
    evaluated_at: datetime | None = None


class MatchedFilingOut(BaseModel):
    filing_id: str
    company_name: str
    filing_date: date
    filing_type: str
    source_authority: str
    source_url: str | None
    determination: str | None


class RumourVerificationOut(BaseModel):
    query_text: str
    rumour_date: date | None
    status: str | None
    matched_score: float | None
    matched_filing: MatchedFilingOut | None
    candidates_considered: int
    candidates_passing: int
    top_candidate_reasons: list[str]
    logged_event_id: str | None
    #: Which Module 5 engine produced this. "n8n_llm_workflow" returns a
    #: verdict plus the workflow's own prose; only
    #: "local_constrained_retrieval" can produce an elimination trace.
    engine: str
    framing_label: str


class CandidateExplanationOut(BaseModel):
    """One candidate filing the local retriever considered -- including the
    ones it rejected, which is the half that makes this an explanation."""

    filing_id: str
    company_name: str
    filing_date: date
    score: float
    passed: bool
    is_winner: bool
    failed_constraints: list[str]
    reasons: list[str]


class LocalRumourVerificationOut(BaseModel):
    query_text: str
    rumour_date: date | None
    status: str | None
    matched_score: float | None
    matched_filing: MatchedFilingOut | None
    candidates_considered: int
    candidates_passing: int
    candidates_eliminated: int
    eliminated_by_constraint: dict[str, int]
    why_ranked_first: str
    candidate_explanations: list[CandidateExplanationOut]
    full_trace_text: str
    logged_event_id: str | None
    engine: str
    framing_label: str
    claim_note: str
