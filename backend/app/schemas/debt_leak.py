from decimal import Decimal

from pydantic import BaseModel


class RecoverableComponentOut(BaseModel):
    component_id: str
    label: str
    annual_amount_paise: int
    explanation: str
    concrete_action: str


class StrategyResultOut(BaseModel):
    strategy: str
    months_to_clear_all: int
    total_interest_paise: int
    payoff_order: tuple[str, ...]
    converged: bool


class AvalancheSnowballOut(BaseModel):
    avalanche: StrategyResultOut
    snowball: StrategyResultOut
    interest_saved_by_avalanche_paise: int
    months_saved_by_avalanche: int


class PrepayVsInvestOut(BaseModel):
    debt_id: str
    guaranteed_annual_rate_pct: Decimal
    extra_monthly_paise: int
    baseline_months: int
    baseline_total_interest_paise: int
    accelerated_months: int
    accelerated_total_interest_paise: int
    interest_saved_paise: int
    months_saved: int
    framing_note: str


class DebtLeakReportOut(BaseModel):
    total_recoverable_annual_paise: int
    components: list[RecoverableComponentOut]
    data_source_note: str
    expense_source_mode: str
    expense_source_is_explicit: bool
    avalanche_snowball: AvalancheSnowballOut | None
    prepay_vs_invest: PrepayVsInvestOut | None


class CreditCardRevolvingCostIn(BaseModel):
    balance_paise: int
    monthly_rate_bps: int
    min_payment_pct_bps: int
    min_payment_floor_paise: int


class CreditCardRevolvingCostOut(BaseModel):
    nominal_annual_rate_pct: Decimal
    effective_annual_rate_pct: Decimal
    months_to_clear_at_minimum: int
    total_interest_at_minimum_paise: int
    converged: bool


class RefinanceBreakevenIn(BaseModel):
    emi_id: str
    new_annual_rate_bps: int
    fees_paise: int


class RefinanceBreakevenOut(BaseModel):
    current_monthly_payment_paise: int
    new_monthly_payment_paise: int
    monthly_savings_paise: int
    fees_paise: int
    breakeven_month: int | None
    beneficial: bool
