import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserMonthlySnapshot(Base):
    """One row per user per calendar month.

    Money fields (income/surplus/cash) are integer paise, per the project's
    money-handling convention. `debt_to_income_ratio` and
    `buffer_coverage_months` are ratios, not money, and are stored as exact
    Decimal (SQL NUMERIC) rather than float so downstream comparisons and
    caps stay deterministic.
    """

    __tablename__ = "user_monthly_snapshot"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_user_monthly_snapshot_user_month"),)

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    # first day of the covered calendar month, e.g. 2026-09-01
    month: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    income: Mapped[int] = mapped_column(BigInteger, nullable=False)
    surplus: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cash: Mapped[int] = mapped_column(BigInteger, nullable=False)

    debt_to_income_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    buffer_coverage_months: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
