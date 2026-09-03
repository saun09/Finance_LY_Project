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
