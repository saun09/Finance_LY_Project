from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.onboarding import (
    EmiIn,
    EmiOut,
    ExpenseItemIn,
    ExpenseItemOut,
    ExpenseSourceDecisionIn,
    ExpenseSourceModeOut,
    FinancialPositionOut,
    HoldingIn,
    HoldingOut,
    InsurancePolicyIn,
    InsurancePolicyOut,
    ProfileIn,
    ProfileOut,
)
from app.schemas.user_monthly_snapshot import UserMonthlySnapshotRead
from app.services.onboarding import (
    EmiNotFoundError,
    ExpenseItemNotFoundError,
    ProfileNotFoundError,
    add_emi,
    add_expense_item,
    add_holding,
    add_insurance_policy,
    close_emi,
    complete_onboarding,
    compute_financial_position,
    get_expense_source_mode,
    get_profile,
    list_emis,
    list_expense_items,
    list_holdings,
    list_insurance_policies,
    record_expense_source_decision,
    remove_expense_item,
    upsert_profile,
)

router = APIRouter(prefix="/users/{user_id}", tags=["onboarding"])


def _not_found_as_404(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (ProfileNotFoundError, EmiNotFoundError, ExpenseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/profile", response_model=ProfileOut)
def put_profile(user_id: str, body: ProfileIn, session: Session = Depends(get_session)):
    return upsert_profile(session, user_id=user_id, **body.model_dump())


@router.get("/profile", response_model=ProfileOut)
def get_profile_route(user_id: str, session: Session = Depends(get_session)):
    profile = get_profile(session, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"no profile for user_id={user_id!r}")
    return profile


@router.post("/emis", response_model=EmiOut)
def post_emi(user_id: str, body: EmiIn, session: Session = Depends(get_session)):
    return _not_found_as_404(add_emi, session, user_id=user_id, **body.model_dump())


@router.get("/emis", response_model=list[EmiOut])
def get_emis(user_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(list_emis, session, user_id)


@router.post("/insurance-policies", response_model=InsurancePolicyOut)
def post_insurance_policy(user_id: str, body: InsurancePolicyIn, session: Session = Depends(get_session)):
    return _not_found_as_404(add_insurance_policy, session, user_id=user_id, **body.model_dump())


@router.get("/insurance-policies", response_model=list[InsurancePolicyOut])
def get_insurance_policies(user_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(list_insurance_policies, session, user_id)


@router.post("/holdings", response_model=HoldingOut)
def post_holding(user_id: str, body: HoldingIn, session: Session = Depends(get_session)):
    return _not_found_as_404(add_holding, session, user_id=user_id, **body.model_dump())


@router.get("/holdings", response_model=list[HoldingOut])
def get_holdings(user_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(list_holdings, session, user_id)


@router.post("/expenses", response_model=ExpenseItemOut)
def post_expense_item(user_id: str, body: ExpenseItemIn, session: Session = Depends(get_session)):
    return _not_found_as_404(add_expense_item, session, user_id=user_id, **body.model_dump())


@router.get("/expenses", response_model=list[ExpenseItemOut])
def get_expenses(user_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(list_expense_items, session, user_id)


@router.post("/emis/{emi_id}/close", response_model=EmiOut)
def post_close_emi(user_id: str, emi_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(close_emi, session, user_id=user_id, emi_id=emi_id)


@router.post("/expenses/{item_id}/remove", response_model=ExpenseItemOut)
def post_remove_expense_item(user_id: str, item_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(remove_expense_item, session, user_id=user_id, item_id=item_id)


@router.put("/expense-source-decision", response_model=ExpenseSourceModeOut)
def put_expense_source_decision(user_id: str, body: ExpenseSourceDecisionIn, session: Session = Depends(get_session)):
    _not_found_as_404(record_expense_source_decision, session, user_id=user_id, decision=body.decision)
    resolved = get_expense_source_mode(session, user_id)
    return ExpenseSourceModeOut(**resolved.__dict__)


@router.get("/expense-source-decision", response_model=ExpenseSourceModeOut)
def get_expense_source_decision(user_id: str, session: Session = Depends(get_session)):
    resolved = _not_found_as_404(get_expense_source_mode, session, user_id)
    return ExpenseSourceModeOut(**resolved.__dict__)


@router.get("/financial-position", response_model=FinancialPositionOut)
def get_financial_position(user_id: str, session: Session = Depends(get_session)):
    return _not_found_as_404(compute_financial_position, session, user_id)


@router.post("/complete-onboarding", response_model=UserMonthlySnapshotRead)
def post_complete_onboarding(user_id: str, session: Session = Depends(get_session)):
    _profile, snapshot = _not_found_as_404(complete_onboarding, session, user_id)
    return snapshot
