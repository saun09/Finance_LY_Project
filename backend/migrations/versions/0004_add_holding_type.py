"""add holding_type to holding table (Module 4 classification input)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

holding_type_enum = sa.Enum(
    "savings_account", "liquid_or_overnight_fund", "fixed_deposit", "recurring_deposit",
    "debt_mutual_fund", "ppf", "epf", "direct_equity", "equity_mutual_fund", "elss",
    "hybrid_mutual_fund_aggressive", "hybrid_mutual_fund_balanced", "hybrid_mutual_fund_conservative",
    "nps", "gold_etf", "sovereign_gold_bond", "physical_gold", "real_estate_direct", "reit_invit",
    "p2p_lending", "cryptocurrency", "unlisted_equity_or_aif", "ulip", "endowment_or_moneyback_policy",
    name="holding_type_enum",
)


def upgrade() -> None:
    holding_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("holding", sa.Column("holding_type", holding_type_enum, nullable=True))


def downgrade() -> None:
    op.drop_column("holding", "holding_type")
    holding_type_enum.drop(op.get_bind(), checkfirst=True)
