"""Versioned Layer 1 risk-ladder bounds and Layer 2 capital market
assumptions for Module 4 (Module 3's final risk tier -> Module 4's target
allocation).

Module 4 runs a two-layer hybrid, adapted from a standalone risk-score/
Sharpe-optimizer prototype into this project's tier-based pipeline:

- Layer 1 (this config's RISK_LADDER_BOUNDS_V1) sets a deterministic,
  auditable [min, max] weight range per asset class for a given final
  tier. `final_tier` here is already the output of Module 3's "ability
  before willingness" capacity-ceiling capping (compute_final_tier), so
  this layer does not re-derive a separate debt/emergency-fund safety
  override from raw profile fields the way the original prototype did --
  that enforcement already happened before `final_tier` reaches Module 4.
- Layer 2 (allocation.py) then picks the Sharpe-maximizing point inside
  Layer 1's bounds using this config's CAPITAL_MARKET_ASSUMPTIONS_V1.

CAPITAL_MARKET_ASSUMPTIONS_V1 is a deliberately simple, illustrative set
of long-run annualized return/volatility/correlation assumptions per
asset class -- NOT a market forecast, NOT updated live, and NOT specific
to any fund/scheme/security (same category-level-only boundary as
asset_classification_config.py's decomposition assumptions). A revision
to these numbers is a new version here, not a silent edit, since it
changes every user's suggested split.

v3-hybrid revises the Layer 1 risk-ladder bounds (widened cash/debt
ranges at the conservative end, a nonzero alternatives ceiling at tier 1)
and the Layer 2 capital market assumptions (debt/real-assets/alternatives
expected returns, real-assets/alternatives volatility and all pairwise
correlations, and the risk-free rate) to align with an updated set of
benchmark-derived defaults. v2-hybrid's values remain available in
version-control history.
"""

from app.services.asset_classification_config import AssetClass

# Per-tier [min, max] weight bounds in percent (0-100), one range per
# asset class. v2 realigns these ranges to the Module 4 hybrid engine's
# updated risk ladder (widened cash/debt ranges for the conservative tiers,
# and a per-tier alternatives ceiling instead of a hard [0, 0] at tier 1)
# so Layer 2 has room to optimize within a tier while every other module's
# 5-asset-class AssetClass contract still holds.
RISK_LADDER_BOUNDS_V1: dict[int, dict[AssetClass, tuple[float, float]]] = {
    1: {
        AssetClass.CASH: (15.0, 30.0),
        AssetClass.DEBT: (55.0, 75.0),
        AssetClass.EQUITY: (0.0, 15.0),
        AssetClass.REAL_ASSETS: (0.0, 10.0),
        AssetClass.ALTERNATIVES: (0.0, 5.0),
    },
    2: {
        AssetClass.CASH: (10.0, 20.0),
        AssetClass.DEBT: (45.0, 65.0),
        AssetClass.EQUITY: (15.0, 30.0),
        AssetClass.REAL_ASSETS: (0.0, 12.0),
        AssetClass.ALTERNATIVES: (0.0, 7.0),
    },
    3: {
        AssetClass.CASH: (5.0, 15.0),
        AssetClass.DEBT: (30.0, 50.0),
        AssetClass.EQUITY: (30.0, 50.0),
        AssetClass.REAL_ASSETS: (5.0, 15.0),
        AssetClass.ALTERNATIVES: (0.0, 10.0),
    },
    4: {
        AssetClass.CASH: (3.0, 10.0),
        AssetClass.DEBT: (15.0, 35.0),
        AssetClass.EQUITY: (45.0, 65.0),
        AssetClass.REAL_ASSETS: (5.0, 15.0),
        AssetClass.ALTERNATIVES: (3.0, 12.0),
    },
    5: {
        AssetClass.CASH: (2.0, 8.0),
        AssetClass.DEBT: (5.0, 20.0),
        AssetClass.EQUITY: (60.0, 80.0),
        AssetClass.REAL_ASSETS: (5.0, 15.0),
        AssetClass.ALTERNATIVES: (5.0, 15.0),
    },
}

for _tier, _bounds in RISK_LADDER_BOUNDS_V1.items():
    _min_sum = sum(b[0] for b in _bounds.values())
    _max_sum = sum(b[1] for b in _bounds.values())
    assert _min_sum <= 100.0, f"tier {_tier}: Layer 1 min bounds sum to {_min_sum} > 100 -- infeasible"
    assert _max_sum >= 100.0, f"tier {_tier}: Layer 1 max bounds sum to {_max_sum} < 100 -- infeasible"

# Illustrative long-run annualized assumptions (decimals: 0.12 = 12%). Not
# a forecast; see module docstring. v2 realigns these to the Module 4
# hybrid engine's benchmark-derived fallback defaults (Nifty 50 TRI /
# CRISIL Composite Bond Fund Index / 91-day T-Bill / gold+REIT blend /
# international-equity proxy).
_EXPECTED_RETURN: dict[AssetClass, float] = {
    AssetClass.CASH: 0.045,
    AssetClass.DEBT: 0.075,
    AssetClass.EQUITY: 0.120,
    AssetClass.REAL_ASSETS: 0.090,
    AssetClass.ALTERNATIVES: 0.100,
}

# Volatility and correlation are derived from Module 4's raw annualized
# covariance matrix (vol_i = sqrt(cov_ii), corr_ij = cov_ij / (vol_i *
# vol_j)) to fit this module's vol/correlation representation.
_VOLATILITY: dict[AssetClass, float] = {
    AssetClass.CASH: 0.010,
    AssetClass.DEBT: 0.050,
    AssetClass.EQUITY: 0.200,
    AssetClass.REAL_ASSETS: 0.148,
    AssetClass.ALTERNATIVES: 0.173,
}

_CORRELATION: dict[tuple[AssetClass, AssetClass], float] = {
    (AssetClass.CASH, AssetClass.DEBT): 0.06,
    (AssetClass.CASH, AssetClass.EQUITY): 0.01,
    (AssetClass.CASH, AssetClass.REAL_ASSETS): 0.007,
    (AssetClass.CASH, AssetClass.ALTERNATIVES): 0.012,
    (AssetClass.DEBT, AssetClass.EQUITY): 0.20,
    (AssetClass.DEBT, AssetClass.REAL_ASSETS): 0.054,
    (AssetClass.DEBT, AssetClass.ALTERNATIVES): 0.069,
    (AssetClass.EQUITY, AssetClass.REAL_ASSETS): 0.203,
    (AssetClass.EQUITY, AssetClass.ALTERNATIVES): 0.347,
    (AssetClass.REAL_ASSETS, AssetClass.ALTERNATIVES): 0.195,
}


def _correlation_of(a: AssetClass, b: AssetClass) -> float:
    if a == b:
        return 1.0
    return _CORRELATION.get((a, b), _CORRELATION.get((b, a)))


class CapitalMarketAssumptions:
    """Expected returns and a derived covariance matrix (correlation x
    volatility_i x volatility_j) for a fixed asset-class ordering, used
    directly as scipy inputs by Layer 2's optimizer."""

    def __init__(self, asset_order: tuple[AssetClass, ...]):
        self.asset_order = asset_order
        self.expected_returns: dict[AssetClass, float] = {a: _EXPECTED_RETURN[a] for a in asset_order}
        self.covariance: dict[tuple[AssetClass, AssetClass], float] = {
            (a, b): _correlation_of(a, b) * _VOLATILITY[a] * _VOLATILITY[b] for a in asset_order for b in asset_order
        }


ASSET_ORDER_V1: tuple[AssetClass, ...] = (
    AssetClass.CASH,
    AssetClass.DEBT,
    AssetClass.EQUITY,
    AssetClass.REAL_ASSETS,
    AssetClass.ALTERNATIVES,
)

CAPITAL_MARKET_ASSUMPTIONS_V1 = CapitalMarketAssumptions(ASSET_ORDER_V1)

# Assumed annualized risk-free rate (91-day T-Bill proxy) used by Layer 2's
# Sharpe-ratio objective.
RISK_FREE_RATE_V1 = 0.045

CONFIG_VERSION = "v3-hybrid"
CONFIG_EFFECTIVE_DATE = "2026-09-17"
