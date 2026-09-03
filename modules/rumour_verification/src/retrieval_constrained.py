"""Constrained retrieval: the TF-IDF baseline plus three structured filters.

(a) entity constraint     — the filing must concern the company named in
                             the rumour, not just share similar words.
(b) temporal constraint   — the filing date must fall in a plausible window
                             *after* the rumour date (a filing can't verify
                             a rumour that hadn't happened yet).
(c) source-authority       — the candidate must be an official exchange
    constraint                filing, not a news article describing one.

Each candidate's per-constraint pass/fail is kept (not just the final
survivors) so a caller can explain *why* a filing ranked where it did —
this trace is exactly what the demo path in verification.py surfaces.
"""

import re
from dataclasses import dataclass
from datetime import date

from src.corpus import Filing
from src.retrieval_baseline import ScoredFiling, TfidfRetriever

DEFAULT_MAX_DAYS_AFTER = 45  # generous plausible-response window

_LEGAL_SUFFIX_RE = re.compile(r"\b(ltd|limited)\b\.?", re.IGNORECASE)


def normalize_company_name(name: str) -> str:
    return re.sub(r"\s+", " ", _LEGAL_SUFFIX_RE.sub("", name).strip().lower())


def mentioned_companies(text: str, corpus: list[Filing]) -> set[str]:
    """Which corpus companies are named (by name or ticker) in `text`."""
    text_lower = text.lower()
    mentioned = set()
    for filing in corpus:
        normalized = normalize_company_name(filing.company_name)
        if normalized and normalized in text_lower:
            mentioned.add(normalized)
            continue
        for ticker in (filing.ticker_bse, filing.ticker_nse):
            if ticker and re.search(rf"\b{re.escape(ticker)}\b", text, re.IGNORECASE):
                mentioned.add(normalized)
                break
    return mentioned


@dataclass(frozen=True)
class ConstraintCheck:
    entity_ok: bool
    temporal_ok: bool
    source_authority_ok: bool
    days_after_rumour: int | None

    @property
    def passed(self) -> bool:
        return self.entity_ok and self.temporal_ok and self.source_authority_ok

    def reasons(self) -> list[str]:
        out = []
        out.append("entity: company matches rumour" if self.entity_ok else "entity: company does not match rumour")
        if self.days_after_rumour is None:
            out.append("temporal: no rumour date supplied")
        elif self.temporal_ok:
            out.append(f"temporal: filed {self.days_after_rumour}d after rumour (within window)")
        else:
            out.append(f"temporal: filed {self.days_after_rumour}d after rumour (outside window)")
        out.append(
            "source: official exchange filing"
            if self.source_authority_ok
            else "source: not an official exchange filing (e.g. news article)"
        )
        return out


@dataclass(frozen=True)
class ConstrainedResult:
    filing: Filing
    score: float
    checks: ConstraintCheck


class ConstrainedRetriever:
    def __init__(
        self,
        corpus: list[Filing],
        baseline: TfidfRetriever | None = None,
        max_days_after: int = DEFAULT_MAX_DAYS_AFTER,
    ):
        self.corpus = corpus
        self.baseline = baseline or TfidfRetriever(corpus)
        self.max_days_after = max_days_after

    def _annotate(
        self,
        candidates: list[ScoredFiling],
        rumour_date: date | None,
        mentioned: set[str],
    ) -> list[ConstrainedResult]:
        results = []
        for c in candidates:
            entity_ok = (not mentioned) or (normalize_company_name(c.filing.company_name) in mentioned)

            if rumour_date is None:
                temporal_ok, days_after = True, None
            else:
                days_after = (c.filing.filing_date - rumour_date).days
                temporal_ok = 0 <= days_after <= self.max_days_after

            source_ok = c.filing.source_authority == "official_exchange_filing"

            results.append(
                ConstrainedResult(
                    filing=c.filing,
                    score=c.score,
                    checks=ConstraintCheck(entity_ok, temporal_ok, source_ok, days_after),
                )
            )
        return results

    def explain(
        self,
        query_text: str,
        rumour_date: date | None = None,
        company_name: str | None = None,
        candidate_pool_size: int | None = None,
    ) -> list[ConstrainedResult]:
        """Return every candidate (pass or fail) with its constraint trace,
        sorted score-descending. Use this for the explainable demo path."""
        pool_size = candidate_pool_size or len(self.corpus)
        candidates = self.baseline.search(query_text, top_k=pool_size)
        mentioned = {normalize_company_name(company_name)} if company_name else mentioned_companies(query_text, self.corpus)
        annotated = self._annotate(candidates, rumour_date, mentioned)
        return sorted(annotated, key=lambda r: r.score, reverse=True)

    def search(
        self,
        query_text: str,
        rumour_date: date | None = None,
        company_name: str | None = None,
        top_k: int = 5,
        candidate_pool_size: int | None = None,
    ) -> list[ConstrainedResult]:
        """Return the top_k constraint-passing candidates, score-descending."""
        annotated = self.explain(query_text, rumour_date, company_name, candidate_pool_size)
        passing = [r for r in annotated if r.checks.passed]
        return passing[:top_k]
