"""encrypt sensitive financial columns at rest (AES-256-GCM, see app/crypto.py)

Each listed column becomes TEXT holding an `enc:v1:` ciphertext, and every
existing row is encrypted in place. Requires DATA_ENCRYPTION_KEY to be set
when this runs -- and the same key afterwards, or the data is unreadable.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-23
"""
import json
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

from app.crypto import EncryptedDecimal, EncryptedInteger, EncryptedJSON, EncryptedString

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# table -> (primary key, [(column, encrypted type, original type, postgres cast)])
COLUMNS = {
    "user_profile": ("user_id", [
        ("income_paise", EncryptedInteger(), sa.BigInteger(), "bigint"),
        ("dependents_count", EncryptedInteger(), sa.Integer(), "integer"),
        ("cash_balance_paise", EncryptedInteger(), sa.BigInteger(), "bigint"),
    ]),
    "emi_entry": ("id", [
        ("lender", EncryptedString(), sa.String(length=128), "varchar(128)"),
        ("amount_paise", EncryptedInteger(), sa.BigInteger(), "bigint"),
        ("remaining_tenure_months", EncryptedInteger(), sa.Integer(), "integer"),
        ("annual_rate_bps", EncryptedInteger(), sa.Integer(), "integer"),
    ]),
    "insurance_policy": ("id", [
        ("sum_assured_paise", EncryptedInteger(), sa.BigInteger(), "bigint"),
    ]),
    "holding": ("id", [
        ("description", EncryptedString(), sa.Text(), "text"),
        ("value_paise", EncryptedInteger(), sa.BigInteger(), "bigint"),
    ]),
    "expense_item": ("id", [
        ("category", EncryptedString(), sa.String(length=64), "varchar(64)"),
        ("amount_paise", EncryptedInteger(), sa.BigInteger(), "bigint"),
    ]),
    "user_monthly_snapshot": ("snapshot_id", [
        ("income", EncryptedInteger(), sa.BigInteger(), "bigint"),
        ("surplus", EncryptedInteger(), sa.BigInteger(), "bigint"),
        ("cash", EncryptedInteger(), sa.BigInteger(), "bigint"),
        ("debt_to_income_ratio", EncryptedDecimal(4), sa.Numeric(precision=6, scale=4), "numeric(6,4)"),
        ("buffer_coverage_months", EncryptedDecimal(2), sa.Numeric(precision=6, scale=2), "numeric(6,2)"),
    ]),
    "suggestion_event": ("event_id", [
        ("suggested_value", EncryptedJSON(), sa.JSON(), "json"),
        ("chosen_value", EncryptedJSON(), sa.JSON(), "json"),
        ("delta", EncryptedJSON(), sa.JSON(), "json"),
        ("market_context", EncryptedJSON(), sa.JSON(), "json"),
    ]),
}


def _parse_plain(enc_type, text: str):
    """Old column value (already cast to TEXT) -> the Python value the
    encrypted type expects."""
    if isinstance(enc_type, EncryptedInteger):
        return int(Decimal(text))
    if isinstance(enc_type, EncryptedDecimal):
        return Decimal(text)
    if isinstance(enc_type, EncryptedJSON):
        return json.loads(text)
    return text


def _format_plain(enc_type, value) -> str:
    """Decrypted Python value -> TEXT the original column type can cast back from."""
    if isinstance(enc_type, EncryptedJSON):
        return json.dumps(value)
    return str(value)


def _rewrite(table: str, pk: str, columns, transform) -> None:
    bind = op.get_bind()
    names = [c[0] for c in columns]
    selected = ", ".join(f'"{n}"' for n in [pk, *names])
    rows = bind.execute(sa.text(f'SELECT {selected} FROM "{table}"')).all()
    assignments = ", ".join(f'"{n}" = :{n}' for n in names)
    update = sa.text(f'UPDATE "{table}" SET {assignments} WHERE "{pk}" = :pk')
    for row in rows:
        params = {"pk": row[0]}
        for (name, enc_type, _, _), value in zip(columns, row[1:]):
            params[name] = None if value is None else transform(enc_type, str(value))
        bind.execute(update, params)


def upgrade() -> None:
    for table, (pk, columns) in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for name, _, orig_type, _ in columns:
                batch.alter_column(
                    name, type_=sa.Text(), existing_type=orig_type, postgresql_using=f'"{name}"::text'
                )
        _rewrite(
            table, pk, columns,
            lambda enc_type, text: enc_type.process_bind_param(_parse_plain(enc_type, text), None),
        )


def downgrade() -> None:
    for table, (pk, columns) in COLUMNS.items():
        _rewrite(
            table, pk, columns,
            lambda enc_type, text: _format_plain(enc_type, enc_type.process_result_value(text, None)),
        )
        with op.batch_alter_table(table) as batch:
            for name, _, orig_type, pg_cast in columns:
                batch.alter_column(
                    name, type_=orig_type, existing_type=sa.Text(), postgresql_using=f'"{name}"::{pg_cast}'
                )
