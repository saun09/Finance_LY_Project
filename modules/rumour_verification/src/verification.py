"""Demo path: a user-pasted rumour -> matched filing -> confirmed/denied/
unaddressed determination, with a full trace.

This only ever verifies a rumour the user explicitly supplies (via
`rumour_text`, and optionally `rumour_date`/`company_name` if known) — it
does not detect or ingest rumours on its own; see the module README for why
that boundary is a hard project constraint, not just a design choice.

The trace this returns is deliberately structured (not just a prose string)
so a later transparency/explainability view can render it directly:
retrieval candidates with scores, which of the three constraints each
passed or failed, which filing was selected, and how its confirmed/denied/
unaddressed status was derived from the filing's own determination plus the
Reg 30(11) 24-hour timeline logic in labels.py.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from src.corpus import Filing
from src.labels import FilingResponse, RumourLabel, classify_rumour_status
from src.retrieval_constrained import ConstrainedRetriever, ConstrainedResult


@dataclass(frozen=True)
class VerificationResult:
    query_text: str
    rumour_date: date | None
    matched_filing: Filing | None
    matched_score: float | None
    status: RumourLabel | None
    candidates: list[ConstrainedResult]  # constraint-passing candidates only, top_k
    all_candidates: list[ConstrainedResult]  # every candidate considered, pass or fail -- what a
    # transparency view needs to show which constraint eliminated which filing, not just the winner

    def explain(self) -> str:
        lines = [f"Rumour: {self.query_text!r}"]
        if self.matched_filing is None:
            lines.append("No filing passed all three constraints (entity, temporal, source-authority).")
        else:
            f = self.matched_filing
            lines.append(f"Matched filing: {f.filing_id} - {f.company_name} ({f.filing_date.isoformat()})")
            lines.append(f"Determination: {self.status}")
            lines.append(f"Similarity score: {self.matched_score:.3f}")
            top = self.candidates[0]
            lines.append("Why this filing ranked first:")
            for reason in top.checks.reasons():
                lines.append(f"  - {reason}")
        lines.append(f"Candidates considered: {len(self.candidates)}")
        return "\n".join(lines)


def verify_rumour(
    rumour_text: str,
    corpus: list[Filing],
    rumour_date: date | None = None,
    company_name: str | None = None,
    evaluated_at: datetime | None = None,
    retriever: ConstrainedRetriever | None = None,
    top_k: int = 5,
    min_score: float = 0.08,
) -> VerificationResult:
    """`min_score` guards against forcing a low-confidence match: the
    entity constraint deliberately no-ops when it can't recognize any
    company name in the text (see mentioned_companies), so an unrelated
    rumour could otherwise still "pass" all three constraints against
    whichever candidate happens to be temporally in-window. A similarity
    floor keeps that case honestly reported as no match rather than a
    confident-looking wrong answer.
    """
    retriever = retriever or ConstrainedRetriever(corpus)
    candidates = retriever.explain(rumour_text, rumour_date=rumour_date, company_name=company_name)
    passing = [c for c in candidates if c.checks.passed and c.score >= min_score][:top_k]

    if not passing:
        return VerificationResult(
            query_text=rumour_text,
            rumour_date=rumour_date,
            matched_filing=None,
            matched_score=None,
            status=None,
            candidates=candidates[:top_k],
            all_candidates=candidates,
        )

    best = passing[0]
    status = None
    if rumour_date is not None:
        mpm_trigger_at = datetime.combine(rumour_date, time.min)
        evaluated_at = evaluated_at or (mpm_trigger_at + timedelta(hours=48))
        response = FilingResponse(
            exists=True,
            filed_at=datetime.combine(best.filing.filing_date, time.min),
            determination=best.filing.determination,
        )
        status = classify_rumour_status(mpm_trigger_at=mpm_trigger_at, evaluated_at=evaluated_at, response=response)

    return VerificationResult(
        query_text=rumour_text,
        rumour_date=rumour_date,
        matched_filing=best.filing,
        matched_score=best.score,
        status=status,
        candidates=passing,
        all_candidates=candidates,
    )
