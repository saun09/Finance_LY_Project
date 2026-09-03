"""Versioned category-level target allocation by final risk tier (Module 3).

Category-level only, per the project's hard legal boundary: this table
never names a fund, stock, or scheme, and never will — it's a simple
lookup from tier (1-5) to a percentage split across the five asset
classes, nothing more. Alternatives exposure is capped low even at tier 5
given its illiquidity and lack of standardized regulation; cash exposure
scales down as tier rises since higher tiers already cleared the capacity
checks (buffer, EMI ratio) that justify holding less idle cash.
"""

from decimal import Decimal

from app.services.asset_classification_config import AssetClass

TARGET_ALLOCATION_TABLE_V1: dict[int, dict[AssetClass, Decimal]] = {
    1: {
        AssetClass.CASH: Decimal("40"),
        AssetClass.DEBT: Decimal("50"),
        AssetClass.EQUITY: Decimal("10"),
        AssetClass.REAL_ASSETS: Decimal("0"),
        AssetClass.ALTERNATIVES: Decimal("0"),
    },
    2: {
        AssetClass.CASH: Decimal("25"),
        AssetClass.DEBT: Decimal("50"),
        AssetClass.EQUITY: Decimal("20"),
        AssetClass.REAL_ASSETS: Decimal("5"),
        AssetClass.ALTERNATIVES: Decimal("0"),
    },
    3: {
        AssetClass.CASH: Decimal("15"),
        AssetClass.DEBT: Decimal("40"),
        AssetClass.EQUITY: Decimal("35"),
        AssetClass.REAL_ASSETS: Decimal("8"),
        AssetClass.ALTERNATIVES: Decimal("2"),
    },
    4: {
        AssetClass.CASH: Decimal("10"),
        AssetClass.DEBT: Decimal("25"),
        AssetClass.EQUITY: Decimal("50"),
        AssetClass.REAL_ASSETS: Decimal("10"),
        AssetClass.ALTERNATIVES: Decimal("5"),
    },
    5: {
        AssetClass.CASH: Decimal("5"),
        AssetClass.DEBT: Decimal("15"),
        AssetClass.EQUITY: Decimal("65"),
        AssetClass.REAL_ASSETS: Decimal("10"),
        AssetClass.ALTERNATIVES: Decimal("5"),
    },
}

assert all(sum(row.values()) == Decimal("100") for row in TARGET_ALLOCATION_TABLE_V1.values())

CONFIG_VERSION = "v1"
CONFIG_EFFECTIVE_DATE = "2026-01-01"
