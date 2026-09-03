"""Onboarding service: profile/EMI/insurance/holdings/expense capture, the
manual-vs-statement-parsing decision, and financial-position computation.

Every mutation that can change net worth, surplus, buffer-months, or the
EMI ratio (profile income/cash, EMI entries, expense items, holdings) is a
"material edit" and re-derives + re-logs the month's snapshot via Module
1's log_monthly_snapshot. Insurance-policy entries and the expense-source
decision record don't feed any of those four metrics, so they don't
trigger a snapshot write.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import (
    EmiEntry,
    EmploymentType,
    ExpenseItem,
    ExpenseSourceDecisionRecord,
    Holding,
    IncomeStability,
    InsurancePolicy,
    InsuranceType,
    UserProfile,
)
from app.services.asset_classification_config import HoldingType
from app.models.user_monthly_snapshot import UserMonthlySnapshot
from app.services.event_log import log_monthly_snapshot
from app.services.expense_source_decision import (
    ExpenseSourceDecisionState,
    ExpenseSourceMode,
    ResolvedExpenseSourceMode,
    resolve_expense_source_mode,
)
from app.services.financial_position import (
    EmiInput,
    ExpenseFrequency,
    ExpenseInput,
    compute_average_monthly_essential_expense,
    compute_emergency_fund_coverage_months,
    compute_emi_to_income_ratio,
    compute_monthly_surplus,
    compute_net_worth,
    compute_total_monthly_emi,
    compute_total_monthly_expenses,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite (used in tests/dev) silently drops tzinfo on round-trip
    through DateTime(timezone=True) columns, unlike Postgres — so a
    datetime read back from the DB can come back naive even though it was
    written as UTC-aware. Every datetime this module writes is UTC, so a
    naive value read back is always safe to re-attach UTC to."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class ProfileNotFoundError(ValueError):
    pass


def get_profile(session: Session, user_id: str) -> UserProfile | None:
    return session.get(UserProfile, user_id)


def upsert_profile(
    session: Session,
    *,
    user_id: str,
    income_paise: int,
    income_stability: IncomeStability,
    employment_type: EmploymentType,
    dependents_count: int = 0,
    cash_balance_paise: int = 0,
    commit: bool = True,
) -> UserProfile:
    profile = session.get(UserProfile, user_id)
    is_new = profile is None
    if profile is None:
        profile = UserProfile(user_id=user_id, onboarding_started_at=_utcnow())
        session.add(profile)

    profile.income_paise = income_paise
    profile.income_stability = income_stability
    profile.employment_type = employment_type
    profile.dependents_count = dependents_count
    profile.cash_balance_paise = cash_balance_paise
    session.flush()

    if is_new:
        _ensure_decision_record(session, user_id, profile.onboarding_started_at)

    if commit:
        session.commit()
        session.refresh(profile)
    _recompute_and_log_snapshot(session, user_id, commit=commit)
    return profile


def list_emis(session: Session, user_id: str) -> list[EmiEntry]:
    """All EMIs ever recorded, oldest first, active and closed alike -- a
    management screen needs to show what was closed, not just what's
    still open (see EmiEntry's own docstring on why closed rows persist)."""
    _require_profile(session, user_id)
    return list(
        session.execute(
            select(EmiEntry).where(EmiEntry.user_id == user_id).order_by(EmiEntry.created_at)
        ).scalars().all()
    )


def add_emi(
    session: Session,
    *,
    user_id: str,
    lender: str,
    amount_paise: int,
    remaining_tenure_months: int,
    annual_rate_bps: int,
    commit: bool = True,
) -> EmiEntry:
    _require_profile(session, user_id)
    emi = EmiEntry(
        user_id=user_id,
        lender=lender,
        amount_paise=amount_paise,
        remaining_tenure_months=remaining_tenure_months,
        annual_rate_bps=annual_rate_bps,
    )
    session.add(emi)
    session.flush()
    if commit:
        session.commit()
        session.refresh(emi)
    _recompute_and_log_snapshot(session, user_id, commit=commit)
    return emi


class EmiNotFoundError(ValueError):
    pass


def close_emi(session: Session, *, user_id: str, emi_id: str, closed_at: datetime | None = None, commit: bool = True) -> EmiEntry:
    """Mark an EMI as fully paid off. Excluded from financial-position
    calculations from this point on, but the row stays (with `closed_at`
    set) so history -- e.g. Module 10's "debt cleared" milestone -- can
    still see it existed."""
    _require_profile(session, user_id)
    emi = session.get(EmiEntry, emi_id)
    if emi is None or emi.user_id != user_id:
        raise EmiNotFoundError(f"no EMI id={emi_id!r} for user_id={user_id!r}")

    emi.closed_at = closed_at or _utcnow()
    session.flush()
    if commit:
        session.commit()
        session.refresh(emi)
    _recompute_and_log_snapshot(session, user_id, commit=commit)
    return emi


def list_insurance_policies(session: Session, user_id: str) -> list[InsurancePolicy]:
    _require_profile(session, user_id)
    return list(
        session.execute(
            select(InsurancePolicy).where(InsurancePolicy.user_id == user_id).order_by(InsurancePolicy.created_at)
        ).scalars().all()
    )


def add_insurance_policy(
    session: Session,
    *,
    user_id: str,
    policy_type: InsuranceType,
    sum_assured_paise: int,
    commit: bool = True,
) -> InsurancePolicy:
    _require_profile(session, user_id)
    policy = InsurancePolicy(user_id=user_id, policy_type=policy_type, sum_assured_paise=sum_assured_paise)
    session.add(policy)
    session.flush()
    if commit:
        session.commit()
        session.refresh(policy)
    return policy  # not a material edit for the four computed metrics — no snapshot write


def list_holdings(session: Session, user_id: str) -> list[Holding]:
    _require_profile(session, user_id)
    return list(
        session.execute(
            select(Holding).where(Holding.user_id == user_id).order_by(Holding.created_at)
        ).scalars().all()
    )


def add_holding(
    session: Session,
    *,
    user_id: str,
    description: str,
    value_paise: int,
    holding_type: HoldingType | None = None,
    commit: bool = True,
) -> Holding:
    _require_profile(session, user_id)
    holding = Holding(user_id=user_id, description=description, value_paise=value_paise, holding_type=holding_type)
    session.add(holding)
    session.flush()
    if commit:
        session.commit()
        session.refresh(holding)
    _recompute_and_log_snapshot(session, user_id, commit=commit)
    return holding


def list_expense_items(session: Session, user_id: str) -> list[ExpenseItem]:
    """All expense items ever recorded, oldest first, active and removed
    alike (see ExpenseItem's own docstring on why removed rows persist)."""
    _require_profile(session, user_id)
    return list(
        session.execute(
            select(ExpenseItem).where(ExpenseItem.user_id == user_id).order_by(ExpenseItem.created_at)
        ).scalars().all()
    )


def add_expense_item(
    session: Session,
    *,
    user_id: str,
    category: str,
    amount_paise: int,
    frequency: ExpenseFrequency,
    is_essential: bool,
    commit: bool = True,
) -> ExpenseItem:
    _require_profile(session, user_id)
    item = ExpenseItem(
        user_id=user_id,
        category=category,
        amount_paise=amount_paise,
        frequency=frequency,
        is_essential=is_essential,
    )
    session.add(item)
    session.flush()
    if commit:
        session.commit()
        session.refresh(item)
    _recompute_and_log_snapshot(session, user_id, commit=commit)
    return item


class ExpenseItemNotFoundError(ValueError):
    pass


def remove_expense_item(session: Session, *, user_id: str, item_id: str, removed_at: datetime | None = None, commit: bool = True) -> ExpenseItem:
    """Mark a recurring expense as cancelled/no longer active. Excluded
    from financial-position calculations from this point on; the row
    stays (with `removed_at` set) so Module 10's "subscription cancelled"
    milestone can see it existed and was cancelled."""
    _require_profile(session, user_id)
    item = session.get(ExpenseItem, item_id)
    if item is None or item.user_id != user_id:
        raise ExpenseItemNotFoundError(f"no expense item id={item_id!r} for user_id={user_id!r}")

    item.removed_at = removed_at or _utcnow()
    session.flush()
    if commit:
        session.commit()
        session.refresh(item)
    _recompute_and_log_snapshot(session, user_id, commit=commit)
    return item


def _ensure_decision_record(session: Session, user_id: str, onboarding_started_at: datetime) -> ExpenseSourceDecisionRecord:
    record = session.get(ExpenseSourceDecisionRecord, user_id)
    if record is None:
        record = ExpenseSourceDecisionRecord(user_id=user_id, onboarding_started_at=onboarding_started_at)
        session.add(record)
        session.flush()
    return record


def record_expense_source_decision(
    session: Session,
    *,
    user_id: str,
    decision: ExpenseSourceMode,
    decided_at: datetime | None = None,
    commit: bool = True,
) -> ExpenseSourceDecisionRecord:
    profile = _require_profile(session, user_id)
    record = _ensure_decision_record(session, user_id, profile.onboarding_started_at)
    record.decision = decision
    record.decided_at = decided_at or _utcnow()
    if commit:
        session.commit()
        session.refresh(record)
    else:
        session.flush()
    return record


def get_expense_source_mode(
    session: Session, user_id: str, evaluated_at: datetime | None = None
) -> ResolvedExpenseSourceMode:
    profile = _require_profile(session, user_id)
    record = _ensure_decision_record(session, user_id, profile.onboarding_started_at)
    session.flush()
    state = ExpenseSourceDecisionState(
        onboarding_started_at=_as_utc(record.onboarding_started_at),
        decision=record.decision,
        decided_at=_as_utc(record.decided_at) if record.decided_at else None,
    )
    return resolve_expense_source_mode(state, _as_utc(evaluated_at or _utcnow()))


def _require_profile(session: Session, user_id: str) -> UserProfile:
    profile = session.get(UserProfile, user_id)
    if profile is None:
        raise ProfileNotFoundError(f"no user_profile for user_id={user_id!r}; call upsert_profile first")
    return profile


def _gather_inputs(session: Session, user_id: str) -> tuple[UserProfile, list[EmiInput], list[ExpenseInput], list[int]]:
    profile = _require_profile(session, user_id)

    emi_rows = session.execute(
        select(EmiEntry).where(EmiEntry.user_id == user_id, EmiEntry.closed_at.is_(None))
    ).scalars().all()
    emis = [
        EmiInput(amount_paise=e.amount_paise, remaining_tenure_months=e.remaining_tenure_months, annual_rate_bps=e.annual_rate_bps)
        for e in emi_rows
    ]

    expense_rows = session.execute(
        select(ExpenseItem).where(ExpenseItem.user_id == user_id, ExpenseItem.removed_at.is_(None))
    ).scalars().all()
    expenses = [
        ExpenseInput(amount_paise=e.amount_paise, frequency=e.frequency, is_essential=e.is_essential)
        for e in expense_rows
    ]

    holding_rows = session.execute(select(Holding).where(Holding.user_id == user_id)).scalars().all()
    holdings_paise = [h.value_paise for h in holding_rows]

    return profile, emis, expenses, holdings_paise


def compute_financial_position(session: Session, user_id: str) -> dict:
    """Pure-function outputs, gathered from the user's current stored
    inputs. Every figure here is re-derivable from user_profile/emi_entry/
    expense_item/holding rows, which is how this stays traceable without a
    separate reasoning-inputs blob on the snapshot table itself."""
    profile, emis, expenses, holdings_paise = _gather_inputs(session, user_id)

    total_monthly_emi = compute_total_monthly_emi(emis)
    total_monthly_expenses = compute_total_monthly_expenses(expenses)
    essential_monthly_expense = compute_average_monthly_essential_expense(expenses)

    return {
        "net_worth_paise": compute_net_worth(profile.cash_balance_paise, holdings_paise, emis),
        "monthly_surplus_paise": compute_monthly_surplus(profile.income_paise, total_monthly_expenses, total_monthly_emi),
        "buffer_coverage_months": compute_emergency_fund_coverage_months(profile.cash_balance_paise, essential_monthly_expense),
        "emi_to_income_ratio": compute_emi_to_income_ratio(total_monthly_emi, profile.income_paise),
        "total_monthly_expenses_paise": total_monthly_expenses,
        "essential_monthly_expense_paise": essential_monthly_expense,
        "total_monthly_emi_paise": total_monthly_emi,
    }


def _recompute_and_log_snapshot(session: Session, user_id: str, month: date | None = None, commit: bool = True) -> UserMonthlySnapshot:
    profile = _require_profile(session, user_id)
    position = compute_financial_position(session, user_id)
    snapshot_month = month or _utcnow().date().replace(day=1)

    return log_monthly_snapshot(
        session,
        user_id=user_id,
        month=snapshot_month,
        income=profile.income_paise,
        surplus=position["monthly_surplus_paise"],
        cash=profile.cash_balance_paise,
        debt_to_income_ratio=position["emi_to_income_ratio"],
        buffer_coverage_months=position["buffer_coverage_months"],
        commit=commit,
    )


def complete_onboarding(session: Session, user_id: str, completed_at: datetime | None = None, commit: bool = True) -> tuple[UserProfile, UserMonthlySnapshot]:
    profile = _require_profile(session, user_id)
    profile.onboarding_completed_at = completed_at or _utcnow()
    session.flush()
    if commit:
        session.commit()
        session.refresh(profile)

    snapshot = _recompute_and_log_snapshot(session, user_id, commit=commit)
    return profile, snapshot
