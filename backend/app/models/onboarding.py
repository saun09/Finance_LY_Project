import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.services.asset_classification_config import HoldingType
from app.services.expense_source_decision import ExpenseSourceMode
from app.services.financial_position import ExpenseFrequency


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncomeStability(str, enum.Enum):
    REGULAR = "regular"
    IRREGULAR = "irregular"


class EmploymentType(str, enum.Enum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"
    BUSINESS_OWNER = "business_owner"
    FREELANCER = "freelancer"
    UNEMPLOYED = "unemployed"
    OTHER = "other"


class InsuranceType(str, enum.Enum):
    LIFE = "life"
    HEALTH = "health"


class UserProfile(Base):
    """One row per user: the core onboarding profile. `cash_balance_paise`
    is the user's declared liquid cash+equivalents, used directly (and only
    this field, not holdings) as the numerator of emergency-fund coverage —
    see financial_position.compute_emergency_fund_coverage_months."""

    __tablename__ = "user_profile"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    income_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    income_stability: Mapped[IncomeStability] = mapped_column(
        Enum(IncomeStability, name="income_stability_enum"), nullable=False
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType, name="employment_type_enum"), nullable=False
    )
    dependents_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cash_balance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    onboarding_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class EmiEntry(Base):
    """One row per EMI/loan the user reports. `amount_paise` is the monthly
    EMI payment itself (not the outstanding principal, which onboarding
    doesn't collect directly — it's derived; see
    financial_position.compute_outstanding_principal). `closed_at` is
    nullable (None = still active); a closed EMI is excluded from ongoing
    financial-position calculations but stays in the table so history
    (e.g. Module 10's "debt cleared" milestone) can still see it existed."""

    __tablename__ = "emi_entry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profile.user_id"), index=True, nullable=False)

    lender: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    remaining_tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InsurancePolicy(Base):
    __tablename__ = "insurance_policy"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profile.user_id"), index=True, nullable=False)

    policy_type: Mapped[InsuranceType] = mapped_column(Enum(InsuranceType, name="insurance_type_enum"), nullable=False)
    sum_assured_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Holding(Base):
    """Savings/investment entry. `description` is a freeform user label
    (never surfaced by Module 4's classification outputs, logs, or
    aggregates — only `holding_type` and computed numbers are). `holding_type`
    is nullable because Module 2 predates Module 4's classification
    taxonomy and some rows may still be unclassified; Module 4 requires it
    to be set before a holding can be classified, and errors clearly
    rather than guessing when it isn't."""

    __tablename__ = "holding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profile.user_id"), index=True, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    value_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    holding_type: Mapped[HoldingType | None] = mapped_column(Enum(HoldingType, name="holding_type_enum"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ExpenseItem(Base):
    """`removed_at` is nullable (None = still active); a removed item is
    excluded from ongoing financial-position calculations but stays in the
    table so Module 10's "subscription cancelled" milestone can see it
    existed and was cancelled, not just deleted without a trace."""

    __tablename__ = "expense_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profile.user_id"), index=True, nullable=False)

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    frequency: Mapped[ExpenseFrequency] = mapped_column(Enum(ExpenseFrequency, name="expense_frequency_enum"), nullable=False)
    is_essential: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExpenseSourceDecisionRecord(Base):
    """One row per user: whether/when the manual-vs-statement-parsing
    decision was made. See app/services/expense_source_decision.py for the
    pure resolution logic this record feeds."""

    __tablename__ = "expense_source_decision"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profile.user_id"), primary_key=True)
    onboarding_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision: Mapped[ExpenseSourceMode | None] = mapped_column(
        Enum(ExpenseSourceMode, name="expense_source_mode_enum"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
