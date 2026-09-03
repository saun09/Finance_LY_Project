from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.debt_leak import (
    CreditCardRevolvingCostIn,
    CreditCardRevolvingCostOut,
    DebtLeakReportOut,
    RefinanceBreakevenIn,
    RefinanceBreakevenOut,
)
from app.services.debt_engine import credit_card_revolving_cost
from app.services.debt_leak_service import EmiNotFoundError, compute_and_log_debt_leak_report, compute_refinance_breakeven_for_emi
from app.services.onboarding import ProfileNotFoundError

router = APIRouter(prefix="/users/{user_id}/debt-leak", tags=["debt_leak"])


@router.get("", response_model=DebtLeakReportOut)
def get_debt_leak_report(user_id: str, session: Session = Depends(get_session)):
    try:
        report = compute_and_log_debt_leak_report(session, user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DebtLeakReportOut(
        total_recoverable_annual_paise=report.total_recoverable_annual_paise,
        components=[
            {
                "component_id": c.component_id,
                "label": c.label,
                "annual_amount_paise": c.annual_amount_paise,
                "explanation": c.explanation,
                "concrete_action": c.concrete_action,
            }
            for c in report.leak.components
        ],
        data_source_note=report.leak.data_source_note,
        expense_source_mode=report.expense_source_mode,
        expense_source_is_explicit=report.expense_source_is_explicit,
        avalanche_snowball=None
        if report.avalanche_snowball is None
        else {
            "avalanche": report.avalanche_snowball.avalanche.__dict__,
            "snowball": report.avalanche_snowball.snowball.__dict__,
            "interest_saved_by_avalanche_paise": report.avalanche_snowball.interest_saved_by_avalanche_paise,
            "months_saved_by_avalanche": report.avalanche_snowball.months_saved_by_avalanche,
        },
        prepay_vs_invest=None if report.prepay_vs_invest is None else report.prepay_vs_invest.__dict__,
    )


@router.post("/credit-card-revolving-cost", response_model=CreditCardRevolvingCostOut)
def post_credit_card_revolving_cost(user_id: str, body: CreditCardRevolvingCostIn):
    return credit_card_revolving_cost(**body.model_dump())


@router.post("/refinance-breakeven", response_model=RefinanceBreakevenOut)
def post_refinance_breakeven(user_id: str, body: RefinanceBreakevenIn, session: Session = Depends(get_session)):
    try:
        return compute_refinance_breakeven_for_emi(session, user_id, body.emi_id, body.new_annual_rate_bps, body.fees_paise)
    except EmiNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
