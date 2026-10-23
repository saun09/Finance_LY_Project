import base64
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cryptography.exceptions import InvalidTag

from app import crypto
from app.models import Holding, SuggestionEvent, UserMonthlySnapshot, UserProfile
from app.models.onboarding import EmploymentType, IncomeStability

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _raw(session, sql: str):
    return session.execute(sa.text(sql)).scalar_one()


def test_sensitive_columns_are_ciphertext_in_the_database_and_plain_through_the_orm(session):
    session.add(UserProfile(
        user_id="u1", income_paise=12_345_600, income_stability=IncomeStability.REGULAR,
        employment_type=EmploymentType.SALARIED, dependents_count=2, cash_balance_paise=999_000,
    ))
    session.add(Holding(user_id="u1", description="HDFC FD ending 4821", value_paise=50_000_000))
    session.add(UserMonthlySnapshot(
        user_id="u1", month=date(2026, 10, 1), income=12_345_600, surplus=1_000, cash=999_000,
        debt_to_income_ratio=Decimal("0.123456"), buffer_coverage_months=Decimal("3.456"),
    ))
    session.add(SuggestionEvent(user_id="u1", module_source="allocation", suggested_value={"amount_paise": 777}))
    session.commit()

    raw_income = _raw(session, "SELECT income_paise FROM user_profile")
    raw_desc = _raw(session, "SELECT description FROM holding")
    raw_event = _raw(session, "SELECT suggested_value FROM suggestion_event")
    for raw, secret in [(raw_income, "12345600"), (raw_desc, "HDFC"), (raw_event, "777")]:
        assert raw.startswith(crypto.PREFIX)
        assert secret not in raw

    session.expire_all()
    profile = session.get(UserProfile, "u1")
    assert profile.income_paise == 12_345_600 and isinstance(profile.income_paise, int)
    assert profile.dependents_count == 2
    holding = session.execute(sa.select(Holding)).scalar_one()
    assert holding.description == "HDFC FD ending 4821"
    snapshot = session.execute(sa.select(UserMonthlySnapshot)).scalar_one()
    # quantized to the NUMERIC(6,4)/(6,2) scales the columns had before encryption
    assert snapshot.debt_to_income_ratio == Decimal("0.1235")
    assert snapshot.buffer_coverage_months == Decimal("3.46")
    event = session.execute(sa.select(SuggestionEvent)).scalar_one()
    assert event.suggested_value == {"amount_paise": 777}
    assert event.chosen_value is None


def test_same_plaintext_encrypts_differently_each_time():
    assert crypto.encrypt("42") != crypto.encrypt("42")


def test_tampered_ciphertext_is_rejected():
    token = crypto.encrypt("12345")
    blob = bytearray(base64.urlsafe_b64decode(token[len(crypto.PREFIX):]))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        crypto.decrypt(crypto.PREFIX + base64.urlsafe_b64encode(bytes(blob)).decode())


def test_unencrypted_value_is_rejected_rather_than_passed_through():
    with pytest.raises(ValueError):
        crypto.decrypt("12345")


def test_wrong_key_cannot_decrypt(monkeypatch):
    token = crypto.encrypt("12345")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", crypto.generate_key())
    crypto._aesgcm.cache_clear()
    try:
        with pytest.raises(InvalidTag):
            crypto.decrypt(token)
    finally:
        monkeypatch.undo()
        crypto._aesgcm.cache_clear()


def test_missing_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("DATA_ENCRYPTION_KEY")
    crypto._aesgcm.cache_clear()
    try:
        with pytest.raises(crypto.EncryptionKeyError):
            crypto.encrypt("x")
    finally:
        monkeypatch.undo()
        crypto._aesgcm.cache_clear()


def test_migration_0010_encrypts_existing_rows_and_downgrade_restores_them(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'enc.db'}"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "0009")
    engine = sa.create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO user_profile (user_id, income_paise, income_stability, employment_type, "
            "dependents_count, cash_balance_paise, onboarding_started_at, created_at, updated_at) "
            "VALUES ('u1', 5000000, 'REGULAR', 'SALARIED', 1, 250000, '2026-10-01', '2026-10-01', '2026-10-01')"
        ))
        conn.execute(sa.text(
            "INSERT INTO suggestion_event (event_id, user_id, timestamp, module_source, suggested_value, "
            "market_context, created_at) VALUES ('e1', 'u1', '2026-10-01', 'allocation', "
            "'{\"amount_paise\": 777}', '{}', '2026-10-01')"
        ))

    command.upgrade(cfg, "0010")
    with engine.connect() as conn:
        raw_income = conn.execute(sa.text("SELECT income_paise FROM user_profile")).scalar_one()
        raw_event = conn.execute(sa.text("SELECT suggested_value FROM suggestion_event")).scalar_one()
    assert raw_income.startswith(crypto.PREFIX) and crypto.decrypt(raw_income) == "5000000"
    assert raw_event.startswith(crypto.PREFIX) and crypto.decrypt(raw_event) == '{"amount_paise": 777}'

    command.downgrade(cfg, "0009")
    with engine.connect() as conn:
        assert int(conn.execute(sa.text("SELECT income_paise FROM user_profile")).scalar_one()) == 5_000_000
    engine.dispose()


def test_https_is_enforced_when_force_https_is_on(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main

    monkeypatch.setattr(app.main, "FORCE_HTTPS", True)
    client = TestClient(app.main.app)

    redirected = client.get("/health", headers={"X-Forwarded-Proto": "http"}, follow_redirects=False)
    assert redirected.status_code == 308
    assert redirected.headers["location"].startswith("https://")

    ok = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert ok.status_code == 200
    assert "max-age" in ok.headers["strict-transport-security"]
