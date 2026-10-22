"""add offset_pct_points to suggestion_event (Module 7's equity offset in effect when shown)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suggestion_event", sa.Column("offset_pct_points", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("suggestion_event", "offset_pct_points")
