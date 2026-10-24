"""create nudge_conversation and nudge_message (stored voice-assistant conversations)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nudge_conversation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("elevenlabs_conversation_id", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_nudge_conversation_user_id", "nudge_conversation", ["user_id"])

    op.create_table(
        "nudge_message",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("nudge_conversation.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nudge_message_conversation_id", "nudge_message", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_nudge_message_conversation_id", table_name="nudge_message")
    op.drop_table("nudge_message")
    op.drop_index("ix_nudge_conversation_user_id", table_name="nudge_conversation")
    op.drop_table("nudge_conversation")
