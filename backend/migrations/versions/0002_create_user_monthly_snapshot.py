"""create user_monthly_snapshot table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_monthly_snapshot",
        sa.Column("snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("income", sa.BigInteger(), nullable=False),
        sa.Column("surplus", sa.BigInteger(), nullable=False),
        sa.Column("cash", sa.BigInteger(), nullable=False),
        sa.Column("debt_to_income_ratio", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("buffer_coverage_months", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "month", name="uq_user_monthly_snapshot_user_month"),
    )
    op.create_index("ix_user_monthly_snapshot_user_id", "user_monthly_snapshot", ["user_id"])
    op.create_index("ix_user_monthly_snapshot_month", "user_monthly_snapshot", ["month"])


def downgrade() -> None:
    op.drop_index("ix_user_monthly_snapshot_month", table_name="user_monthly_snapshot")
    op.drop_index("ix_user_monthly_snapshot_user_id", table_name="user_monthly_snapshot")
    op.drop_table("user_monthly_snapshot")
