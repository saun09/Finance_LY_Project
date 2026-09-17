"""add purpose to emi_entry (what the loan is for -- home/vehicle/...)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

emi_purpose_enum = sa.Enum(
    "home", "vehicle", "personal", "education", "credit_card", "electronics", "other",
    name="emi_purpose_enum",
)


def upgrade() -> None:
    emi_purpose_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("emi_entry", sa.Column("purpose", emi_purpose_enum, nullable=True))


def downgrade() -> None:
    op.drop_column("emi_entry", "purpose")
    emi_purpose_enum.drop(op.get_bind(), checkfirst=True)
