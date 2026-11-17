"""Bridge between the FastAPI backend and the n8n Module 5 workflow."""

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models.suggestion_event import SuggestionEvent
from app.services.event_log import log_suggestion_event

# `os.getenv` only sees real process environment variables, not .env files --
# app.config loads backend/.env too, but only once it's imported, so without this N8N_WEBHOOK_URL is
# silently unset regardless of what's in the file. `load_dotenv` never
# overrides a variable already set in the real environment (e.g. in CI or a
# test's monkeypatch), so this is a no-op wherever the env var is set another way.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

#: Recorded on every event this bridge logs so Module 9 can tell the two
#: Module 5 engines apart. See rumour_local_engine.py for the other one.
N8N_ENGINE_NAME = "n8n_llm_workflow"

#: How long to wait for n8n to *accept* a run. The workflow itself takes
#: minutes and reports back via callback (see rumour_verification_job.py);
#: its Webhook node responds immediately, so this only covers the hand-off.
N8N_START_TIMEOUT_SECONDS = 30.0


class N8NTimeoutError(RuntimeError):
    """n8n didn't accept the run within N8N_START_TIMEOUT_SECONDS."""


class N8NVerificationResult:
    """Normalized representation of the JSON returned by n8n."""

    def __init__(
        self,
        query_text: str,
        rumour_date: date | None,
        verdict: str | None,
        confidence: float | None,
        company: str,
        ticker: str,
        official_evidence: list[dict[str, Any]],
        news_evidence: list[dict[str, Any]],
        temporal_analysis: str,
        reasoning: str,
        caveats: list[str],
    ):
        self.query_text = query_text
        self.rumour_date = rumour_date
        self.verdict = verdict
        self.confidence = confidence
        self.company = company
        self.ticker = ticker
        self.official_evidence = official_evidence
        self.news_evidence = news_evidence
        self.temporal_analysis = temporal_analysis
        self.reasoning = reasoning
        self.caveats = caveats


def start_verification(
    rumour_text: str,
    *,
    job_id: str,
    callback_url: str,
    callback_token: str,
    rumour_date: date | None = None,
    company_name: str | None = None,
    evaluated_at: datetime | None = None,
) -> None:
    """Hand a rumour to the n8n workflow and return once n8n has accepted
    it. The verdict arrives later: the workflow's last node POSTs its
    output to `callback_url` with `X-Callback-Token: <callback_token>`.

    Raises RuntimeError (N8NTimeoutError for a timeout) if n8n can't be
    reached or refuses the run."""
    if not N8N_WEBHOOK_URL:
        raise RuntimeError("N8N_WEBHOOK_URL is not configured.")

    # The workflow's existing fields, plus what it needs to report back.
    payload = {
        "rumour": rumour_text,
        "company": company_name or "",
        "ticker": company_name or "",
        "rumour_date": rumour_date.isoformat() if rumour_date else "",
        "evaluated_at": evaluated_at.isoformat() if evaluated_at else "",
        "job_id": job_id,
        "callback_url": callback_url,
        "callback_token": callback_token,
    }

    try:
        response = httpx.post(N8N_WEBHOOK_URL, json=payload, timeout=N8N_START_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise N8NTimeoutError("The broader workflow didn't respond. Try again shortly.") from exc
    except httpx.HTTPStatusError as exc:
        # n8n Cloud's error pages are full HTML documents -- only the status
        # is useful to a user.
        raise RuntimeError(
            f"The broader workflow refused the request (HTTP {exc.response.status_code}). Try again shortly."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not connect to the broader workflow: {exc}") from exc


def parse_n8n_result(
    data: Any,
    *,
    rumour_text: str,
    rumour_date: date | None = None,
    company_name: str | None = None,
) -> N8NVerificationResult:
    """Normalize the workflow's final JSON (what its callback POSTs)."""
    if not isinstance(data, dict):
        raise RuntimeError(
            f"n8n returned a malformed response (expected a JSON object, got {type(data).__name__})."
        )

    official_evidence = data.get("official_evidence")
    if not isinstance(official_evidence, list):
        official_evidence = []

    news_evidence = data.get("news_evidence")
    if not isinstance(news_evidence, list):
        news_evidence = []

    confidence = data.get("confidence")
    if confidence is not None and not isinstance(confidence, (int, float)):
        confidence = None

    caveats = data.get("caveats")
    if not isinstance(caveats, list):
        caveats = []

    return N8NVerificationResult(
        query_text=data.get("claim") or rumour_text,
        rumour_date=rumour_date,
        verdict=data.get("verdict"),
        confidence=confidence,
        company=data.get("company") or company_name or "",
        ticker=data.get("ticker") or "",
        official_evidence=official_evidence,
        news_evidence=news_evidence,
        temporal_analysis=data.get("temporal_analysis") or "",
        reasoning=data.get("reasoning") or "",
        caveats=[c for c in caveats if isinstance(c, str)],
    )


def _extract_matched_filing(result: N8NVerificationResult) -> dict | None:
    """Build matched_filing from n8n's best official-evidence item, but
    only when that item actually names a specific, dated, sourced filing.
    An evidence entry missing an id/date/authority isn't "no information",
    it's *insufficient* information -- surfacing it anyway (with blank or
    guessed fallbacks) would present a fabricated filing as real, and a
    raw `date` object slipping into `filing_date` here would also fail to
    JSON-serialize when logged. Empty/insufficient evidence both resolve
    to `None`, per the response contract's "matched_filing must be null"
    rule.
    """
    if not result.official_evidence:
        return None

    best = result.official_evidence[0]
    if not isinstance(best, dict):
        return None

    filing_id = best.get("filing_id") or best.get("id")
    filing_date = best.get("filing_date") or best.get("date")
    source_authority = best.get("source_authority") or best.get("source")

    if not filing_id or not filing_date or not source_authority:
        return None

    return {
        "filing_id": filing_id,
        "company_name": best.get("company_name") or result.company,
        "filing_date": filing_date,
        "filing_type": best.get("filing_type") or best.get("type") or "",
        "source_authority": source_authority,
        "source_url": best.get("source_url") or best.get("url"),
        "determination": best.get("determination") or best.get("determination_status"),
    }


def verification_result_to_suggested_value(
    result: N8NVerificationResult,
) -> dict:

    matched_filing = _extract_matched_filing(result)

    return {
        "query_text": result.query_text,
        "rumour_date": (
            result.rumour_date.isoformat()
            if result.rumour_date
            else None
        ),
        "status": result.verdict,
        "matched_score": result.confidence,
        "matched_filing": matched_filing,
        "candidates_considered": (
            len(result.official_evidence)
            + len(result.news_evidence)
        ),
        "candidates_passing": len(result.official_evidence),
        # filter out blanks -- n8n doesn't always populate reasoning/temporal
        # analysis, and a list of empty strings isn't a useful "reasons" list
        "top_candidate_reasons": [r for r in (result.reasoning, result.temporal_analysis, *result.caveats) if r],
    }


def log_verification_event(
    session: Session,
    user_id: str,
    result: N8NVerificationResult,
) -> SuggestionEvent:

    suggested_value = verification_result_to_suggested_value(result)

    return log_suggestion_event(
        session,
        user_id=user_id,
        module_source="rumour_verification",
        suggested_value=suggested_value,
        market_context={
            # Which engine produced this. Module 9 reads it to label the
            # trace honestly: this path is an external LLM workflow whose
            # prose reasoning is a self-report, NOT the constraint-
            # elimination explanation the local engine produces (see
            # app/services/rumour_local_engine.py). Without this field the
            # two are indistinguishable in the log.
            "engine": N8N_ENGINE_NAME,
            "official_evidence_count": len(
                result.official_evidence
            ),
            "news_evidence_count": len(
                result.news_evidence
            ),
            "verdict": result.verdict,
            "confidence": result.confidence,
        },
    )