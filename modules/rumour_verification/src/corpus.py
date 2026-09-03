"""Loading helpers for the filings corpus and rumour dataset."""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Filing:
    filing_id: str
    company_name: str
    ticker_bse: str | None
    ticker_nse: str | None
    filing_date: date
    filing_type: str
    filing_text: str
    source_authority: str  # "official_exchange_filing" | "news_article"
    source_url: str | None
    is_real: bool
    determination: str | None  # "confirms" | "denies" | "non_committal" | None


@dataclass(frozen=True)
class RumourCase:
    rumour_id: str
    company_name: str
    ticker_bse: str | None
    ticker_nse: str | None
    rumour_text: str
    rumour_date: date
    matching_filing_id: str
    label: str


def _parse_date(s: str) -> date:
    y, m, d = (int(part) for part in s.split("-"))
    return date(y, m, d)


def load_corpus(path: Path | None = None) -> list[Filing]:
    path = path or (DATA_DIR / "filings_corpus.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        Filing(
            filing_id=d["filing_id"],
            company_name=d["company_name"],
            ticker_bse=d.get("ticker_bse"),
            ticker_nse=d.get("ticker_nse"),
            filing_date=_parse_date(d["filing_date"]),
            filing_type=d["filing_type"],
            filing_text=d["filing_text"],
            source_authority=d["source_authority"],
            source_url=d.get("source_url"),
            is_real=d["is_real"],
            determination=d.get("determination"),
        )
        for d in raw
    ]


def load_rumour_dataset(path: Path | None = None) -> list[RumourCase]:
    path = path or (DATA_DIR / "rumour_dataset.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        RumourCase(
            rumour_id=d["rumour_id"],
            company_name=d["company_name"],
            ticker_bse=d.get("ticker_bse"),
            ticker_nse=d.get("ticker_nse"),
            rumour_text=d["rumour_text"],
            rumour_date=_parse_date(d["rumour_date"]),
            matching_filing_id=d["matching_filing_id"],
            label=d["label"],
        )
        for d in raw
    ]
