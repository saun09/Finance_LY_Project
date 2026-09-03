"""Wires Module 4's pure classification/allocation logic to Module 2's
holdings, Module 3's final tier, and Module 1's event log. This is the
only layer in Module 4 that touches the database or Module 1/2/3's
services directly — classify_holding, aggregate_classifications, and
compute_target_allocation are pure and independently tested.

Hard constraint enforced here, not just documented: nothing built into the
logged suggested_value/market_context ever includes a holding's freeform
`description` — only `holding_id` (an opaque UUID) and `holding_type`
(a category value) leave this module.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import Holding
from app.services.allocation import TargetAllocationResult, compute_target_allocation
from app.services.allocation_config import CONFIG_VERSION as ALLOCATION_CONFIG_VERSION
from app.services.asset_classification import (
    HoldingClassification,
    PortfolioClassification,
    aggregate_classifications,
    classify_holding,
)
from app.services.asset_classification_config import CONFIG_VERSION as CLASSIFICATION_CONFIG_VERSION
from app.services.event_log import get_user_event_history, log_suggestion_event


class UnclassifiedHoldingsError(ValueError):
    pass


class NoRiskTierError(ValueError):
    pass


@dataclass(frozen=True)
class AllocationReport:
    portfolio: PortfolioClassification
    target: TargetAllocationResult


def gather_holding_classifications(session: Session, user_id: str) -> list[HoldingClassification]:
    holdings = session.execute(select(Holding).where(Holding.user_id == user_id)).scalars().all()

    unclassified_ids = [h.id for h in holdings if h.holding_type is None]
    if unclassified_ids:
        raise UnclassifiedHoldingsError(
            f"user_id={user_id!r} has holdings without a holding_type set: {unclassified_ids}. "
            "Set holding_type on each (see app.services.asset_classification_config.HoldingType) "
            "before allocation can be computed."
        )

    return [classify_holding(h.id, h.holding_type, h.value_paise) for h in holdings]


def get_latest_final_tier(session: Session, user_id: str) -> int:
    events = get_user_event_history(session, user_id, module_source="risk_profile", limit=1)
    if not events:
        raise NoRiskTierError(f"no risk_profile computation found for user_id={user_id!r}; compute Module 3's tier first")
    return events[0].suggested_value["final_tier"]


def compute_and_log_allocation(session: Session, user_id: str, commit: bool = True) -> AllocationReport:
    classifications = gather_holding_classifications(session, user_id)
    portfolio = aggregate_classifications(classifications)

    final_tier = get_latest_final_tier(session, user_id)
    target = compute_target_allocation(final_tier)

    log_suggestion_event(
        session,
        user_id=user_id,
        module_source="allocation",
        tier=str(final_tier),
        suggested_value={
            "final_tier": target.final_tier,
            "rule_table_version": target.rule_table_version,
            "reasoning": target.reasoning,
            "target_pct": {ac.value: str(pct) for ac, pct in target.target_pct.items()},
            "current_exposure_pct": {ac.value: str(pct) for ac, pct in portfolio.exposure_by_asset_class_pct.items()},
            "current_exposure_paise": {ac.value: paise for ac, paise in portfolio.exposure_by_asset_class_paise.items()},
            "total_value_paise": portfolio.total_value_paise,
            "concentration": {
                "largest_holding_pct": str(portfolio.concentration.largest_holding_pct),
                "largest_holding_id": portfolio.concentration.largest_holding_id,
                "asset_class_hhi_bps": portfolio.concentration.asset_class_hhi_bps,
            },
            "liquidity_breakdown_paise": {liq.value: paise for liq, paise in portfolio.liquidity_breakdown_paise.items()},
            "tax_treatment_breakdown_paise": dict(portfolio.tax_treatment_breakdown_paise),
            "holdings": [
                {
                    "holding_id": c.holding_id,
                    "holding_type": c.holding_type.value,
                    "value_paise": c.value_paise,
                    "decomposition_paise": {ac.value: p for ac, p in c.decomposition_paise.items()},
                    "liquidity": c.liquidity.value,
                    "lock_in_months": c.lock_in_months,
                    "tax_treatment_category": c.tax_treatment_category,
                    "is_look_through": c.is_look_through,
                }
                for c in classifications
            ],
        },
        market_context={
            "asset_classification_config_version": CLASSIFICATION_CONFIG_VERSION,
            "allocation_config_version": ALLOCATION_CONFIG_VERSION,
        },
        commit=commit,
    )

    return AllocationReport(portfolio=portfolio, target=target)
