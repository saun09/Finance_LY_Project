"""create suggestion_event table

Revision ID: 0001
Revises:
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

action_taken_enum = sa.Enum(
    "accepted", "edited", "rejected", "ignored", name="action_taken_enum"
)


def upgrade() -> None:
    op.create_table(
        "suggestion_event",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("module_source", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=True),
        sa.Column("offset", sa.Integer(), nullable=True),
        sa.Column("suggested_value", sa.JSON(), nullable=False),
        sa.Column("chosen_value", sa.JSON(), nullable=True),
        sa.Column("delta", sa.JSON(), nullable=True),
        sa.Column("action_taken", action_taken_enum, nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("funded", sa.Boolean(), nullable=True),
        sa.Column("market_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_suggestion_event_user_id", "suggestion_event", ["user_id"])
    op.create_index("ix_suggestion_event_timestamp", "suggestion_event", ["timestamp"])
    op.create_index("ix_suggestion_event_module_source", "suggestion_event", ["module_source"])


def downgrade() -> None:
    op.drop_index("ix_suggestion_event_module_source", table_name="suggestion_event")
    op.drop_index("ix_suggestion_event_timestamp", table_name="suggestion_event")
    op.drop_index("ix_suggestion_event_user_id", table_name="suggestion_event")
    op.drop_table("suggestion_event")
    action_taken_enum.drop(op.get_bind(), checkfirst=True)
