"""add closed_at to emi_entry, removed_at to expense_item (Module 10 needs
a way to detect "debt cleared" / "subscription cancelled" -- both were
structurally undetectable before this, since Module 2's CRUD was add-only)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("emi_entry", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expense_item", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("expense_item", "removed_at")
    op.drop_column("emi_entry", "closed_at")
