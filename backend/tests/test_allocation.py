from decimal import Decimal

import pytest

from app.services.allocation import compute_target_allocation
from app.services.asset_classification_config import AssetClass


@pytest.mark.parametrize("tier", [1, 2, 3, 4, 5])
def test_every_tier_sums_to_100_percent(tier):
    result = compute_target_allocation(tier)
    assert sum(result.target_pct.values()) == Decimal("100")


def test_tier_1_is_conservative_low_equity_high_cash_debt():
    result = compute_target_allocation(1)
    assert result.target_pct[AssetClass.EQUITY] == Decimal("10")
    assert result.target_pct[AssetClass.CASH] + result.target_pct[AssetClass.DEBT] == Decimal("90")
    assert result.target_pct[AssetClass.ALTERNATIVES] == Decimal("0")


def test_tier_5_is_aggressive_high_equity_low_cash():
    result = compute_target_allocation(5)
    assert result.target_pct[AssetClass.EQUITY] == Decimal("65")
    assert result.target_pct[AssetClass.CASH] == Decimal("5")


def test_equity_allocation_increases_monotonically_with_tier():
    equity_by_tier = [compute_target_allocation(t).target_pct[AssetClass.EQUITY] for t in range(1, 6)]
    assert equity_by_tier == sorted(equity_by_tier)
    assert len(set(equity_by_tier)) == 5  # strictly increasing, no ties


def test_reasoning_trace_names_the_tier_and_rule_table_version():
    result = compute_target_allocation(3)
    assert result.final_tier == 3
    assert result.rule_table_version == "v1"
    assert "tier 3" in result.reasoning
    assert "v1" in result.reasoning


def test_unknown_tier_raises_value_error():
    with pytest.raises(ValueError):
        compute_target_allocation(6)
