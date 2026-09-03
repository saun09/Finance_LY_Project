"""create onboarding tables (Module 2)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

income_stability_enum = sa.Enum("regular", "irregular", name="income_stability_enum")
employment_type_enum = sa.Enum(
    "salaried", "self_employed", "business_owner", "freelancer", "unemployed", "other",
    name="employment_type_enum",
)
insurance_type_enum = sa.Enum("life", "health", name="insurance_type_enum")
expense_frequency_enum = sa.Enum("monthly", "annual", "one_time", name="expense_frequency_enum")
expense_source_mode_enum = sa.Enum("manual_only", "statement_parsing_enabled", name="expense_source_mode_enum")


def upgrade() -> None:
    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("income_paise", sa.BigInteger(), nullable=False),
        sa.Column("income_stability", income_stability_enum, nullable=False),
        sa.Column("employment_type", employment_type_enum, nullable=False),
        sa.Column("dependents_count", sa.Integer(), nullable=False),
        sa.Column("cash_balance_paise", sa.BigInteger(), nullable=False),
        sa.Column("onboarding_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "emi_entry",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profile.user_id"), nullable=False),
        sa.Column("lender", sa.String(length=128), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("remaining_tenure_months", sa.Integer(), nullable=False),
        sa.Column("annual_rate_bps", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_emi_entry_user_id", "emi_entry", ["user_id"])

    op.create_table(
        "insurance_policy",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profile.user_id"), nullable=False),
        sa.Column("policy_type", insurance_type_enum, nullable=False),
        sa.Column("sum_assured_paise", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_insurance_policy_user_id", "insurance_policy", ["user_id"])

    op.create_table(
        "holding",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profile.user_id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("value_paise", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_holding_user_id", "holding", ["user_id"])

    op.create_table(
        "expense_item",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profile.user_id"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("frequency", expense_frequency_enum, nullable=False),
        sa.Column("is_essential", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_expense_item_user_id", "expense_item", ["user_id"])

    op.create_table(
        "expense_source_decision",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user_profile.user_id"), primary_key=True),
        sa.Column("onboarding_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision", expense_source_mode_enum, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("expense_source_decision")
    op.drop_index("ix_expense_item_user_id", table_name="expense_item")
    op.drop_table("expense_item")
    op.drop_index("ix_holding_user_id", table_name="holding")
    op.drop_table("holding")
    op.drop_index("ix_insurance_policy_user_id", table_name="insurance_policy")
    op.drop_table("insurance_policy")
    op.drop_index("ix_emi_entry_user_id", table_name="emi_entry")
    op.drop_table("emi_entry")
    op.drop_table("user_profile")

    bind = op.get_bind()
    expense_source_mode_enum.drop(bind, checkfirst=True)
    expense_frequency_enum.drop(bind, checkfirst=True)
    insurance_type_enum.drop(bind, checkfirst=True)
    employment_type_enum.drop(bind, checkfirst=True)
    income_stability_enum.drop(bind, checkfirst=True)
