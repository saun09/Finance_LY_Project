"""Module 4: two-layer hybrid target-allocation engine, keyed by Module 3's
final risk tier (1-5). No I/O -- pure function of tier + config, matching
this project's convention for scoring/allocation logic.

Adapted from a standalone risk-score (1-10) + Sharpe-optimizer prototype:
this version keys off the same 1-5 `final_tier` every other module already
depends on (drift detection's tier ladder, personalization's capacity-
ceiling capping, gamification's tier-change badges), and optimizes across
all 5 of this project's AssetClass values rather than the prototype's
equity/debt/cash-only set.

Layer 1 (deterministic, auditable): RISK_LADDER_BOUNDS_V1 maps the tier to
a [min, max] weight range per asset class. This is the only hard
constraint applied here -- debt/emergency-fund safety enforcement already
happened upstream in Module 3's capacity-ceiling capping
(compute_capacity_ceiling / compute_final_tier caps the *tier itself*
before it ever reaches this function), so Layer 1 does not re-derive a
separate safety override from raw profile fields the way the prototype
did.

Layer 2 (mean-variance): within Layer 1's bounds, SLSQP maximizes the
Sharpe ratio against CAPITAL_MARKET_ASSUMPTIONS_V1's illustrative
long-run return/volatility/correlation assumptions. If the optimizer
fails to converge, this falls back to the midpoint of Layer 1's bounds,
renormalized to sum to 100 -- Layer 1's bounds remain authoritative
either way, so a solver failure degrades to "safe interior point", never
to an out-of-bounds or non-100%-summing result.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from scipy.optimize import minimize

from app.services.allocation_config import (
    CAPITAL_MARKET_ASSUMPTIONS_V1,
    CONFIG_VERSION,
    RISK_FREE_RATE_V1,
    RISK_LADDER_BOUNDS_V1,
    CapitalMarketAssumptions,
)
from app.services.asset_classification_config import AssetClass


@dataclass(frozen=True)
class TargetAllocationResult:
    final_tier: int
    rule_table_version: str
    target_pct: dict[AssetClass, Decimal]
    reasoning: str


def _neg_sharpe(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, risk_free_rate: float) -> float:
    ret = float(np.dot(weights, mu))
    vol = float(np.sqrt(weights.T @ cov @ weights))
    if vol < 1e-12:
        return 1e6  # penalize degenerate zero-vol portfolios
    return -(ret - risk_free_rate) / vol


def _weights_to_pct(weights: np.ndarray, asset_order: tuple[AssetClass, ...]) -> dict[AssetClass, Decimal]:
    pct = {a: Decimal(str(round(w * 100, 10))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for a, w in zip(asset_order, weights)}
    # Any rounding residual is absorbed by the largest weight so the
    # result always sums to exactly 100.00, matching the project's
    # convention for Decimal-percentage outputs (see personalization.py).
    residual = Decimal("100.00") - sum(pct.values())
    if residual != 0:
        largest = max(pct, key=lambda a: pct[a])
        pct[largest] += residual
    return pct


def compute_target_allocation(
    final_tier: int,
    bounds_table: dict[int, dict[AssetClass, tuple[float, float]]] = RISK_LADDER_BOUNDS_V1,
    market_assumptions: CapitalMarketAssumptions = CAPITAL_MARKET_ASSUMPTIONS_V1,
    risk_free_rate: float = RISK_FREE_RATE_V1,
    table_version: str = CONFIG_VERSION,
) -> TargetAllocationResult:
    if final_tier not in bounds_table:
        raise ValueError(f"no Layer 1 risk-ladder bounds defined for tier {final_tier!r} in rule table {table_version}")

    asset_order = market_assumptions.asset_order
    tier_bounds = bounds_table[final_tier]
    scipy_bounds = [(tier_bounds[a][0] / 100.0, tier_bounds[a][1] / 100.0) for a in asset_order]

    mu = np.array([market_assumptions.expected_returns[a] for a in asset_order])
    cov = np.array([[market_assumptions.covariance[(ai, aj)] for aj in asset_order] for ai in asset_order])

    x0 = np.array([(lo + hi) / 2 for lo, hi in scipy_bounds])
    x0 = x0 / x0.sum()

    result = minimize(
        fun=_neg_sharpe,
        x0=x0,
        args=(mu, cov, risk_free_rate),
        method="SLSQP",
        bounds=scipy_bounds,
        constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
        options={"maxiter": 500, "ftol": 1e-10},
    )

    if result.success:
        weights = result.x
        method_note = "Layer 2 Sharpe-maximizing weights within Layer 1 bounds"
    else:
        lo = np.array([b[0] for b in scipy_bounds])
        hi = np.array([b[1] for b in scipy_bounds])
        weights = np.clip(x0, lo, hi)
        weights = weights / weights.sum()
        method_note = f"Layer 2 optimizer did not converge ({result.message}); fell back to Layer 1 bounds midpoint"

    target_pct = _weights_to_pct(weights, asset_order)

    bounds_desc = ", ".join(f"{a.value}=[{tier_bounds[a][0]:.0f}%,{tier_bounds[a][1]:.0f}%]" for a in asset_order)
    reasoning = f"Looked up tier {final_tier} bounds ({bounds_desc}) in rule table {table_version}; {method_note}."

    return TargetAllocationResult(
        final_tier=final_tier,
        rule_table_version=table_version,
        target_pct=target_pct,
        reasoning=reasoning,
    )
