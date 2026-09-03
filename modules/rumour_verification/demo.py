"""CLI demo: paste a rumour, get back the matched filing + determination + trace.

Usage:
    python demo.py "Adani Enterprises shares rally 4% on $686 million investment in not-for-profit healthcare initiative" --date 2025-02-11
    python demo.py "..." --date 2025-02-11 --full-trace   # Module 9: every candidate considered, pass or fail

With no arguments, runs one built-in example.
"""

import argparse
from datetime import date, datetime

from src.corpus import load_corpus
from src.transparency import format_full_trace
from src.verification import verify_rumour

EXAMPLE_RUMOUR = (
    "Adani Enterprises shares rally 4% on $686 million investment in "
    "not-for-profit healthcare initiative"
)
EXAMPLE_DATE = date(2025, 2, 11)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a pasted market rumour against the filings corpus.")
    parser.add_argument("rumour_text", nargs="?", default=EXAMPLE_RUMOUR)
    parser.add_argument("--date", dest="rumour_date", default=None, help="YYYY-MM-DD the rumour was reported")
    parser.add_argument("--company", dest="company_name", default=None, help="Company name, if already known")
    parser.add_argument(
        "--evaluated-at", dest="evaluated_at", default=None, help="YYYY-MM-DDTHH:MM to evaluate 'now' as (testing)"
    )
    parser.add_argument(
        "--full-trace", action="store_true",
        help="Module 9: show every candidate considered, pass or fail, and which constraint eliminated each one",
    )
    args = parser.parse_args()

    rumour_date = date.fromisoformat(args.rumour_date) if args.rumour_date else (
        EXAMPLE_DATE if args.rumour_text == EXAMPLE_RUMOUR else None
    )
    evaluated_at = datetime.fromisoformat(args.evaluated_at) if args.evaluated_at else None

    corpus = load_corpus()
    result = verify_rumour(
        args.rumour_text,
        corpus,
        rumour_date=rumour_date,
        company_name=args.company_name,
        evaluated_at=evaluated_at,
    )
    print(format_full_trace(result) if args.full_trace else result.explain())


if __name__ == "__main__":
    main()
