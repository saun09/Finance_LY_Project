"""Thin bridge from the backend to Module 5 (modules/rumour_verification/),
which lives outside backend/ by design — see that module's own README:
it needed to be buildable and gradeable independently, in week 1, before
Module 1's data substrate existed. Nothing here moves, duplicates, or
modifies any of Module 5's code; it adds Module 5's own `src/` package to
`sys.path` (the same import style Module 5's own files already use
internally, e.g. `from src.corpus import Filing`) and re-exports exactly
what the API route needs.

`log_verification_event` is purely for auditability — it never sets
`action_taken`/`chosen_value`/`funded`, since (per Module 5's own README)
a rumour-verification result isn't something a user accepts/edits/rejects
the way a suggested allocation is; the event log entry exists only so
"a verification was shown to a user" is captured, which matters for a
transparency-focused project even before anyone builds a UI on top of it.
"""

import sys
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

_RUMOUR_VERIFICATION_ROOT = Path(__file__).resolve().parents[3] / "modules" / "rumour_verification"
if str(_RUMOUR_VERIFICATION_ROOT) not in sys.path:
    sys.path.insert(0, str(_RUMOUR_VERIFICATION_ROOT))

from src.corpus import Filing, load_corpus  # noqa: E402
from src.verification import VerificationResult, verify_rumour  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

from app.models.suggestion_event import SuggestionEvent  # noqa: E402
from app.services.event_log import log_suggestion_event  # noqa: E402


@lru_cache(maxsize=1)
def _cached_corpus() -> tuple[Filing, ...]:
    """The corpus is a static, read-only JSON file (see Module 5's own
    data/filings_corpus.json) -- loaded once per process rather than off
    disk on every request."""
    return tuple(load_corpus())


def run_verification(
    rumour_text: str,
    rumour_date: date | None = None,
    company_name: str | None = None,
    evaluated_at: datetime | None = None,
) -> VerificationResult:
    corpus = list(_cached_corpus())
    return verify_rumour(
        rumour_text, corpus, rumour_date=rumour_date, company_name=company_name, evaluated_at=evaluated_at
    )


def verification_result_to_suggested_value(result: VerificationResult) -> dict:
    """Never recomputes anything -- a straight, JSON-safe reshaping of the
    VerificationResult that verify_rumour already produced, for the
    logged event and the API response alike."""
    matched = result.matched_filing
    return {
        "query_text": result.query_text,
        "rumour_date": result.rumour_date.isoformat() if result.rumour_date else None,
        "status": result.status,
        "matched_score": result.matched_score,
        "matched_filing": None
        if matched is None
        else {
            "filing_id": matched.filing_id,
            "company_name": matched.company_name,
            "filing_date": matched.filing_date.isoformat(),
            "filing_type": matched.filing_type,
            "source_authority": matched.source_authority,
            "source_url": matched.source_url,
            "determination": matched.determination,
        },
        "candidates_considered": len(result.all_candidates),
        "candidates_passing": len(result.candidates),
        # result.candidates can be non-empty even with no match (it holds
        # the top unfiltered-ranking candidates as a fallback in that
        # case, not confirmed passers) -- gate on matched_filing, the
        # actual signal of "there was a real winner", not on the list
        # being non-empty.
        "top_candidate_reasons": [] if matched is None else list(result.candidates[0].checks.reasons()),
    }


def log_verification_event(session: Session, user_id: str, result: VerificationResult) -> SuggestionEvent:
    return log_suggestion_event(
        session,
        user_id=user_id,
        module_source="rumour_verification",
        suggested_value=verification_result_to_suggested_value(result),
        market_context={"corpus_size": len(result.all_candidates)},
    )
