from __future__ import annotations

import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from platform import python_version

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.evidence.registry import validate_registry


ROOT = BACKEND_ROOT.parent
RESULTS_PATH = ROOT / "research_artifacts" / "experiments" / "results" / "evidence_registry_summary.md"
IMPACT_ORDER = {
    "direct_capacity": 0,
    "direct_stated_tier": 1,
    "indirect_allocation": 2,
    "no_direct_tier_effect": 3,
}


def build_summary_markdown() -> str:
    from app.evidence.registry import validate_registry

    registry = validate_registry()
    basis_counts = Counter(entry.basis_type for entry in registry.entries)
    status_counts = Counter(entry.verification_status for entry in registry.entries)
    entries = sorted(
        registry.entries,
        key=lambda entry: (
            IMPACT_ORDER[entry.final_tier_impact],
            entry.config_file,
            entry.constant_name,
        ),
    )
    lines = [
        "# Evidence registry summary",
        "",
        f"Registry entries: {len(registry.entries)}.",
        "",
        "## Runtime versions",
        "",
        "| Runtime/library | Version |",
        "|---|---|",
        f"| Python | {python_version()} |",
        f"| pydantic | {version('pydantic')} |",
        "",
        "## Counts by basis type",
        "",
        "| Basis type | Entries |",
        "|---|---:|",
    ]
    lines.extend(f"| {basis_type} | {basis_counts.get(basis_type, 0)} |" for basis_type in (
        "regulatory",
        "industry_guideline",
        "academic",
        "own_policy",
        "illustrative_assumption",
    ))
    lines.extend(
        [
            "",
            "## Counts by verification status",
            "",
            "| Verification status | Entries |",
            "|---|---:|",
        ]
    )
    lines.extend(
        f"| {status} | {status_counts.get(status, 0)} |"
        for status in ("verified", "unverified", "needs_review")
    )
    lines.extend(
        [
            "",
            "## Entries with source fields still marked TO_FILL",
            "",
            "Ordered by expected effect on the final tier: capacity ceilings, stated-tier scoring, allocation behavior, then rules with no direct tier effect. This is a dependency classification from the application pipeline, not a measured causal effect.",
            "",
            "| # | Final-tier impact | Entry ID | Config constant | Value | Basis | Citation | URL | Retrieved |",
            "|---:|---|---|---|---:|---|---|---|---|",
        ]
    )
    to_fill_entries = [
        entry
        for entry in entries
        if any(
            value == "TO_FILL"
            for value in (entry.source_citation, entry.source_url, entry.retrieved_date)
        )
    ]
    lines.extend(
        "| "
        + " | ".join(
            (
                str(index),
                entry.final_tier_impact,
                entry.id,
                f"`{entry.config_file}:{entry.constant_name}`",
                str(entry.value),
                entry.basis_type,
                entry.source_citation,
                entry.source_url,
                entry.retrieved_date,
            )
        )
        + " |"
        for index, entry in enumerate(to_fill_entries, start=1)
    )
    lines.append("")
    return "\n".join(lines)


def main() -> Path:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = build_summary_markdown()
    RESULTS_PATH.write_text(report, encoding="utf-8")
    print(report.split("## Entries with source fields still marked TO_FILL", 1)[0].rstrip())
    print(RESULTS_PATH)
    return RESULTS_PATH


if __name__ == "__main__":
    main()
