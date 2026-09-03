"""Module 4: pure target-allocation lookup by final risk tier. No I/O.

The "rule" that produces a split is deliberately just a table lookup keyed
by tier — simple and auditable by design, not a black box formula, so the
reasoning trace ("which tier, which rule produced this split") is exactly
that: the tier number and the config version it was looked up in.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.allocation_config import TARGET_ALLOCATION_TABLE_V1
from app.services.asset_classification_config import AssetClass


@dataclass(frozen=True)
class TargetAllocationResult:
    final_tier: int
    rule_table_version: str
    target_pct: dict[AssetClass, Decimal]
    reasoning: str


def compute_target_allocation(
    final_tier: int,
    table: dict[int, dict[AssetClass, Decimal]] = TARGET_ALLOCATION_TABLE_V1,
    table_version: str = "v1",
) -> TargetAllocationResult:
    if final_tier not in table:
        raise ValueError(f"no target allocation defined for tier {final_tier!r} in rule table {table_version}")

    return TargetAllocationResult(
        final_tier=final_tier,
        rule_table_version=table_version,
        target_pct=dict(table[final_tier]),
        reasoning=f"Looked up tier {final_tier} in target allocation rule table {table_version}.",
    )
