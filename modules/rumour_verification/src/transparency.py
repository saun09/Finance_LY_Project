"""Module 9's transparency view over Module 5's own trace.

This lives inside modules/rumour_verification/ rather than backend/
because the trace types it reads (VerificationResult, ConstrainedResult)
live here, and Module 5 has no runtime dependency on the backend by
design (see this module's own README). Nothing here recomputes a
verification — `explain_all_candidates` and `format_full_trace` are pure
formatting over the `VerificationResult` that `verify_rumour` already
produced at verification time (specifically `result.all_candidates`,
the full ranked-and-annotated candidate list before it gets filtered down
to the passing subset).

WHY "EXPLANATION" LANGUAGE IS FINE HERE, UNLIKE ELSEWHERE: the backend's
Module 9 transparency layer (backend/app/services/transparency.py) covers
weighted-sum and rule-table decisions (risk tier, allocation, recoverable
Rs/year) and is deliberately labeled "transparent reasoning" everywhere,
never "explainable AI" or "AI-powered" -- printing the weights *is* the
feature, and calling that "explainable AI" would overclaim. Module 5 is
different in kind, not just degree: it runs an actual multi-stage
retrieval and elimination process (TF-IDF ranking, then three independent
constraint checks each of which can eliminate a candidate) where "why did
THIS filing win, and why were THESE others eliminated" is a genuine,
non-trivial question with a real multi-step answer -- not shorthand for
"here are the coefficients." So this file freely uses "explain" /
"explanation." It still never claims "AI" -- TF-IDF cosine similarity and
three rule-based filters aren't a model either, just a retrieval pipeline
worth walking through step by step.
"""

from dataclasses import dataclass

from src.verification import VerificationResult


@dataclass(frozen=True)
class CandidateExplanation:
    filing_id: str
    company_name: str
    filing_date: str
    score: float
    passed: bool
    is_winner: bool
    failed_constraints: tuple[str, ...]  # empty if it passed all three
    reasons: tuple[str, ...]  # one line per constraint, pass or fail


def explain_all_candidates(result: VerificationResult) -> list[CandidateExplanation]:
    """Every candidate Module 5 considered for this query, not just the
    winner -- which constraint(s) eliminated each one that didn't pass."""
    winner_id = result.matched_filing.filing_id if result.matched_filing else None

    explanations = []
    for c in result.all_candidates:
        failed = []
        if not c.checks.entity_ok:
            failed.append("entity")
        if not c.checks.temporal_ok:
            failed.append("temporal")
        if not c.checks.source_authority_ok:
            failed.append("source_authority")

        explanations.append(
            CandidateExplanation(
                filing_id=c.filing.filing_id,
                company_name=c.filing.company_name,
                filing_date=c.filing.filing_date.isoformat(),
                score=c.score,
                passed=c.checks.passed,
                is_winner=(c.filing.filing_id == winner_id),
                failed_constraints=tuple(failed),
                reasons=tuple(c.checks.reasons()),
            )
        )
    return explanations


def format_full_trace(result: VerificationResult) -> str:
    """A human-readable account of every candidate considered: which ones
    were eliminated, by which constraint(s), and why the winner (if any)
    ranked first among the survivors."""
    explanations = explain_all_candidates(result)
    lines = [f"Rumour: {result.query_text!r}", f"Candidates considered: {len(explanations)}", ""]

    passing = [e for e in explanations if e.passed]
    eliminated = [e for e in explanations if not e.passed]

    if result.matched_filing is not None:
        winner = next(e for e in explanations if e.is_winner)
        lines.append(
            f"Winner: {winner.filing_id} ({winner.company_name}, {winner.filing_date}) "
            f"-- similarity score {winner.score:.3f}"
        )
        if len(passing) > 1:
            runner_up = sorted((e for e in passing if not e.is_winner), key=lambda e: e.score, reverse=True)[0]
            lines.append(
                f"Ranked first among {len(passing)} passing candidates because its similarity "
                f"score ({winner.score:.3f}) was the highest of those that passed all three "
                f"constraints (next-best passing: {runner_up.filing_id} at {runner_up.score:.3f})."
            )
        else:
            lines.append("It was the only candidate to pass all three constraints.")
    else:
        lines.append("No candidate passed all three constraints -- no match returned.")

    lines.append("")
    lines.append(f"Eliminated ({len(eliminated)}):")
    if not eliminated:
        lines.append("  (none -- every candidate considered passed all three constraints)")
    for e in eliminated:
        lines.append(f"  {e.filing_id} ({e.company_name}, {e.filing_date}), score {e.score:.3f}")
        lines.append(f"    eliminated by: {', '.join(e.failed_constraints)}")
        for reason in e.reasons:
            lines.append(f"    - {reason}")

    return "\n".join(lines)
