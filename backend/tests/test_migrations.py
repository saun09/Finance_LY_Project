from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_head_creates_expected_schema(tmp_path):
    db_path = tmp_path / "migrated.db"
    db_url = f"sqlite:///{db_path}"

    command.upgrade(_alembic_config(db_url), "head")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert {
        "suggestion_event",
        "user_monthly_snapshot",
        "user_profile",
        "emi_entry",
        "insurance_policy",
        "holding",
        "expense_item",
        "expense_source_decision",
    } <= tables

    event_columns = {c["name"] for c in inspector.get_columns("suggestion_event")}
    assert event_columns == {
        "event_id",
        "user_id",
        "timestamp",
        "module_source",
        "tier",
        "offset",
        "suggested_value",
        "chosen_value",
        "delta",
        "action_taken",
        "reason_code",
        "funded",
        "market_context",
        "created_at",
    }

    snapshot_columns = {c["name"] for c in inspector.get_columns("user_monthly_snapshot")}
    assert snapshot_columns == {
        "snapshot_id",
        "user_id",
        "month",
        "income",
        "surplus",
        "cash",
        "debt_to_income_ratio",
        "buffer_coverage_months",
        "computed_at",
    }

    profile_columns = {c["name"] for c in inspector.get_columns("user_profile")}
    assert profile_columns == {
        "user_id",
        "income_paise",
        "income_stability",
        "employment_type",
        "dependents_count",
        "cash_balance_paise",
        "onboarding_started_at",
        "onboarding_completed_at",
        "created_at",
        "updated_at",
    }

    emi_columns = {c["name"] for c in inspector.get_columns("emi_entry")}
    assert emi_columns == {
        "id",
        "user_id",
        "lender",
        "amount_paise",
        "remaining_tenure_months",
        "annual_rate_bps",
        "created_at",
        "closed_at",
    }

    decision_columns = {c["name"] for c in inspector.get_columns("expense_source_decision")}
    assert decision_columns == {"user_id", "onboarding_started_at", "decision", "decided_at"}

    holding_columns = {c["name"] for c in inspector.get_columns("holding")}
    assert holding_columns == {"id", "user_id", "description", "value_paise", "holding_type", "created_at"}

    expense_columns = {c["name"] for c in inspector.get_columns("expense_item")}
    assert expense_columns == {
        "id", "user_id", "category", "amount_paise", "frequency", "is_essential", "created_at", "removed_at",
    }

    engine.dispose()


def test_alembic_downgrade_removes_tables(tmp_path):
    db_path = tmp_path / "migrated_down.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = sa.create_engine(db_url)
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert "suggestion_event" not in tables
    assert "user_monthly_snapshot" not in tables
    assert "user_profile" not in tables
    assert "expense_source_decision" not in tables
    engine.dispose()
