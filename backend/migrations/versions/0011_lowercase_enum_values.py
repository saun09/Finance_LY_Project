"""store enum columns as their lowercase values, not member names

The models used to write sa.Enum member *names* ("REGULAR") while 0001/0003/
0004/0007 created the Postgres enum types with the lowercase *values*
("regular"). Postgres rejected every such write, so it never holds uppercase
rows; SQLite doesn't enforce enum types and accepted them. Now that the models
pass values_callable=enum_values, existing SQLite rows are lowercased here so
they still load.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-23
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# Every enum member's value is its name lowercased, so lower() is exact.
ENUM_COLUMNS = [
    ("user_profile", "income_stability"),
    ("user_profile", "employment_type"),
    ("emi_entry", "purpose"),
    ("insurance_policy", "policy_type"),
    ("holding", "holding_type"),
    ("expense_item", "frequency"),
    ("expense_source_decision", "decision"),
    ("suggestion_event", "action_taken"),
]


def _rewrite(func: str) -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    for table, column in ENUM_COLUMNS:
        op.execute(f'UPDATE "{table}" SET "{column}" = {func}("{column}") WHERE "{column}" IS NOT NULL')


def upgrade() -> None:
    _rewrite("lower")


def downgrade() -> None:
    _rewrite("upper")
