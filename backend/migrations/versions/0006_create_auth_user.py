"""create auth_user table (real signup/login accounts)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # unique constraint declared inline at create_table time -- SQLite (used
    # in tests) can't ALTER a table to add a constraint after the fact
    op.create_table(
        "auth_user",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_auth_user_username"),
    )
    op.create_index("ix_auth_user_username", "auth_user", ["username"])


def downgrade() -> None:
    op.drop_index("ix_auth_user_username", table_name="auth_user")
    op.drop_table("auth_user")
