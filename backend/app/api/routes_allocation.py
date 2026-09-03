from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.allocation import AllocationReportOut
from app.services.allocation_service import (
    NoRiskTierError,
    UnclassifiedHoldingsError,
    compute_and_log_allocation,
)

router = APIRouter(prefix="/users/{user_id}/allocation", tags=["allocation"])


@router.get("", response_model=AllocationReportOut)
def get_allocation(user_id: str, session: Session = Depends(get_session)):
    try:
        report = compute_and_log_allocation(session, user_id)
    except UnclassifiedHoldingsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NoRiskTierError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    portfolio, target = report.portfolio, report.target
    return AllocationReportOut(
        final_tier=target.final_tier,
        rule_table_version=target.rule_table_version,
        reasoning=target.reasoning,
        target_pct=target.target_pct,
        current_exposure_pct=portfolio.exposure_by_asset_class_pct,
        current_exposure_paise=portfolio.exposure_by_asset_class_paise,
        total_value_paise=portfolio.total_value_paise,
        concentration={
            "largest_holding_pct": portfolio.concentration.largest_holding_pct,
            "largest_holding_id": portfolio.concentration.largest_holding_id,
            "asset_class_hhi_bps": portfolio.concentration.asset_class_hhi_bps,
        },
        liquidity_breakdown_paise=portfolio.liquidity_breakdown_paise,
        tax_treatment_breakdown_paise=portfolio.tax_treatment_breakdown_paise,
        holdings=[
            {
                "holding_id": c.holding_id,
                "holding_type": c.holding_type.value,
                "value_paise": c.value_paise,
                "decomposition_paise": c.decomposition_paise,
                "liquidity": c.liquidity,
                "lock_in_months": c.lock_in_months,
                "tax_treatment_category": c.tax_treatment_category,
                "is_look_through": c.is_look_through,
            }
            for c in portfolio.holdings
        ],
    )
