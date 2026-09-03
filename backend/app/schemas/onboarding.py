from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.onboarding import EmploymentType, IncomeStability, InsuranceType
from app.services.asset_classification_config import HoldingType
from app.services.expense_source_decision import ExpenseSourceMode
from app.services.financial_position import ExpenseFrequency


class ProfileIn(BaseModel):
    income_paise: int
    income_stability: IncomeStability
    employment_type: EmploymentType
    dependents_count: int = 0
    cash_balance_paise: int = 0


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    income_paise: int
    income_stability: IncomeStability
    employment_type: EmploymentType
    dependents_count: int
    cash_balance_paise: int
    onboarding_started_at: datetime
    onboarding_completed_at: datetime | None


class EmiIn(BaseModel):
    lender: str
    amount_paise: int
    remaining_tenure_months: int
    annual_rate_bps: int


class EmiOut(EmiIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class InsurancePolicyIn(BaseModel):
    policy_type: InsuranceType
    sum_assured_paise: int


class InsurancePolicyOut(InsurancePolicyIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class HoldingIn(BaseModel):
    description: str
    value_paise: int
    holding_type: HoldingType | None = None


class HoldingOut(HoldingIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class ExpenseItemIn(BaseModel):
    category: str
    amount_paise: int
    frequency: ExpenseFrequency
    is_essential: bool


class ExpenseItemOut(ExpenseItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class ExpenseSourceDecisionIn(BaseModel):
    decision: ExpenseSourceMode


class ExpenseSourceModeOut(BaseModel):
    mode: ExpenseSourceMode
    is_explicit_decision: bool
    resolved_at: datetime | None


class FinancialPositionOut(BaseModel):
    net_worth_paise: int
    monthly_surplus_paise: int
    buffer_coverage_months: Decimal
    emi_to_income_ratio: Decimal
    total_monthly_expenses_paise: int
    essential_monthly_expense_paise: int
    total_monthly_emi_paise: int
