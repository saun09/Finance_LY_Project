"""create rumour_verification_job (async n8n runs, completed by callback)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rumour_verification_job",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rumour_text", sa.Text(), nullable=False),
        sa.Column("rumour_date", sa.Date(), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("log_event", sa.Boolean(), nullable=False),
        sa.Column("callback_token_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rumour_verification_job_user_id", "rumour_verification_job", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_rumour_verification_job_user_id", table_name="rumour_verification_job")
    op.drop_table("rumour_verification_job")
