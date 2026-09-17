"""Adapter that makes Module 5's *local* constrained-retrieval engine --
and, with it, Module 9's genuine retrieval explanation -- reachable from
the running app.

WHY THIS FILE EXISTS. Module 5 has two engines, and only one of them can
support the project's explainability claim:

  local constrained retrieval (this file)
      TF-IDF ranking over data/filings_corpus.json, then three independent
      constraint checks (entity, temporal, source-authority), each of which
      can eliminate a candidate on its own. "Which constraint eliminated
      which candidate filing, and why did the returned filing rank first"
      has a real, checkable, multi-step answer here, produced by
      modules/rumour_verification/src/transparency.py::format_full_trace.
      This is the engine the explainability claim attaches to, and the one
      evaluated in modules/rumour_verification/eval/.

  n8n workflow (app/services/rumour_verification_bridge.py)
      An external LLM pipeline returning a verdict, a confidence and a
      prose `reasoning` string. That string is the workflow's own
      self-report; this project neither computed nor evaluated it, and
      there is no candidate list to eliminate from. It is useful (it is
      not restricted to a fixed corpus) but it is NOT the explainability
      claim, and Module 9 labels it "third-party workflow output" so the
      two are never conflated in front of a user.

Previously `format_full_trace` was reachable only from
modules/rumour_verification/demo.py, which made the explainability claim
true of the research artifact and false of the shipped app. This adapter
closes that gap: the app can run the local engine, show every eliminated
candidate with the constraint that eliminated it, and log the whole trace
as a suggestion_event so Module 9 can replay it later.

The Module 5 package is imported lazily and by path because it is a
standalone research module with its own dependencies (scikit-learn,
numpy) and no runtime dependency on this backend -- a design property
worth keeping. If those dependencies are absent the app degrades to the
n8n path with an explicit error, never to a silent fallback that would
leave the user thinking they got an explanation they did not get.
"""

import sys
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.suggestion_event import SuggestionEvent
from app.services.event_log import log_suggestion_event

#: modules/rumour_verification/, whose own code imports itself as `src.*`.
MODULE5_ROOT = Path(__file__).resolve().parents[3] / "modules" / "rumour_verification"

ENGINE_NAME = "local_constrained_retrieval"
MODULE_SOURCE = "rumour_verification_local"


class LocalEngineUnavailableError(RuntimeError):
    """Module 5's package or its dependencies could not be imported."""


def _import_module5():
    if str(MODULE5_ROOT) not in sys.path:
        sys.path.insert(0, str(MODULE5_ROOT))
    try:
        from src.corpus import load_corpus  # noqa: PLC0415
        from src.transparency import explain_all_candidates, format_full_trace  # noqa: PLC0415
        from src.verification import verify_rumour  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise LocalEngineUnavailableError(
            "Module 5's local retrieval engine could not be imported from "
            f"{MODULE5_ROOT}: {exc}. Install its requirements "
            "(modules/rumour_verification/requirements.txt) to enable the "
            "explainable retrieval path."
        ) from exc
    return load_corpus, verify_rumour, explain_all_candidates, format_full_trace


@lru_cache(maxsize=1)
def _loaded_corpus() -> list:
    load_corpus, _, _, _ = _import_module5()
    return load_corpus()


def local_engine_available() -> bool:
    """Whether the explainable path can actually run right now. Callers use
    this to offer the engine rather than to silently substitute it."""
    try:
        _import_module5()
        return True
    except LocalEngineUnavailableError:
        return False


def run_local_verification(
    rumour_text: str,
    rumour_date: date | None = None,
    company_name: str | None = None,
    evaluated_at: datetime | None = None,
):
    """Run the local engine and return Module 5's own `VerificationResult`.

    Returned as-is rather than normalized here, because the trace formatter
    reads `result.all_candidates` -- the full ranked-and-annotated candidate
    list *before* filtering to the passing subset. That list is the entire
    reason an elimination trace is possible; flattening it at this boundary
    would throw the explanation away.
    """
    _, verify_rumour, _, _ = _import_module5()
    return verify_rumour(
        rumour_text,
        _loaded_corpus(),
        rumour_date=rumour_date,
        company_name=company_name,
        evaluated_at=evaluated_at,
    )


def explanation_payload(result) -> dict[str, Any]:
    """Module 5's per-candidate explanation, flattened for JSON transport.

    Pure formatting over an already-produced result -- nothing here re-runs
    retrieval or re-checks a constraint, same discipline as the rest of
    Module 9.
    """
    _, _, explain_all_candidates, format_full_trace = _import_module5()

    explanations = explain_all_candidates(result)
    candidates = [
        {
            "filing_id": e.filing_id,
            "company_name": e.company_name,
            "filing_date": e.filing_date,
            "score": round(float(e.score), 6),
            "passed": e.passed,
            "met_score_floor": e.met_score_floor,
            "eligible": e.eligible,
            "is_winner": e.is_winner,
            "failed_constraints": list(e.failed_constraints),
            "reasons": list(e.reasons),
        }
        for e in explanations
    ]
    # "eligible" (passed the three structured constraints AND cleared the
    # similarity floor), not merely "passed": a candidate stopped by the
    # floor was not returned, so counting it as passing would leave the
    # numbers unable to account for the verdict.
    passing = [c for c in candidates if c["eligible"]]
    eliminated = [c for c in candidates if not c["eligible"]]
    winner = next((c for c in candidates if c["is_winner"]), None)

    runner_up = None
    if winner is not None:
        others = sorted((c for c in passing if not c["is_winner"]), key=lambda c: c["score"], reverse=True)
        if others:
            runner_up = {"filing_id": others[0]["filing_id"], "score": others[0]["score"]}

    if winner is None:
        why_first = "No candidate passed all three constraints, so no filing was returned."
    elif runner_up is not None:
        why_first = (
            f"{winner['filing_id']} ranked first because its similarity score "
            f"({winner['score']:.3f}) was the highest among the {len(passing)} candidates that "
            f"passed all three constraints and cleared the similarity floor "
            f"(next best: {runner_up['filing_id']} at "
            f"{runner_up['score']:.3f})."
        )
    else:
        why_first = (
            f"{winner['filing_id']} was the only eligible candidate: it passed all three "
            "constraints (entity, temporal, source-authority) and cleared the similarity floor."
        )

    by_constraint: dict[str, int] = {}
    for c in eliminated:
        for constraint in c["failed_constraints"]:
            by_constraint[constraint] = by_constraint.get(constraint, 0) + 1

    return {
        "candidate_explanations": candidates,
        "candidates_considered": len(candidates),
        "candidates_passing": len(passing),
        "candidates_eliminated": len(eliminated),
        "eliminated_by_constraint": by_constraint,
        "min_score": float(result.min_score),
        "why_ranked_first": why_first,
        "full_trace_text": format_full_trace(result),
    }


def verification_result_to_suggested_value(result) -> dict[str, Any]:
    matched = result.matched_filing
    payload = {
        "query_text": result.query_text,
        "rumour_date": result.rumour_date.isoformat() if result.rumour_date else None,
        "status": str(result.status) if result.status is not None else None,
        "matched_score": round(float(result.matched_score), 6) if result.matched_score is not None else None,
        "matched_filing": (
            None
            if matched is None
            else {
                "filing_id": matched.filing_id,
                "company_name": matched.company_name,
                "filing_date": matched.filing_date.isoformat(),
                "filing_type": matched.filing_type,
                "source_authority": matched.source_authority,
                "source_url": matched.source_url,
                "determination": matched.determination,
            }
        ),
    }
    payload.update(explanation_payload(result))
    return payload


def log_local_verification_event(session: Session, user_id: str, result, commit: bool = True) -> SuggestionEvent:
    """Log the full elimination trace, not just the verdict.

    Storing `candidate_explanations` is what lets Module 9 replay this
    verification months later without re-running TF-IDF -- the same
    read-from-the-log-never-recompute rule the rest of the transparency
    layer follows.
    """
    suggested_value = verification_result_to_suggested_value(result)
    return log_suggestion_event(
        session,
        user_id=user_id,
        module_source=MODULE_SOURCE,
        suggested_value=suggested_value,
        market_context={
            "engine": ENGINE_NAME,
            "corpus_size": len(_loaded_corpus()),
            "constraints_applied": ["entity", "temporal", "source_authority", "score_floor"],
            "min_score": float(result.min_score),
        },
        commit=commit,
    )
