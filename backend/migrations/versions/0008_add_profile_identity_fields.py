"""add identity fields to user_profile (full_name, email, date_of_birth,
phone_number) -- all nullable, user-entered only, never backfilled

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
    op.add_column("user_profile", sa.Column("full_name", sa.String(128), nullable=True))
    op.add_column("user_profile", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("user_profile", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("user_profile", sa.Column("phone_number", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profile", "phone_number")
    op.drop_column("user_profile", "date_of_birth")
    op.drop_column("user_profile", "email")
    op.drop_column("user_profile", "full_name")
