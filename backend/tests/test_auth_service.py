import pytest

from app.services.auth_service import (
    InvalidCredentialsError,
    UsernameTakenError,
    WeakPasswordError,
    login,
    signup,
)


def test_signup_creates_a_user_with_a_hashed_not_plaintext_password(session):
    user = signup(session, "alice", "correct horse battery")
    assert user.username == "alice"
    assert user.password_hash != "correct horse battery"
    assert user.user_id


def test_signup_rejects_a_duplicate_username(session):
    signup(session, "alice", "correct horse battery")
    with pytest.raises(UsernameTakenError):
        signup(session, "alice", "a different password")


def test_signup_rejects_a_short_password(session):
    with pytest.raises(WeakPasswordError):
        signup(session, "bob", "short")


def test_signup_rejects_a_blank_username(session):
    with pytest.raises(ValueError):
        signup(session, "   ", "correct horse battery")


def test_login_succeeds_with_the_right_password(session):
    created = signup(session, "alice", "correct horse battery")
    logged_in = login(session, "alice", "correct horse battery")
    assert logged_in.user_id == created.user_id


def test_login_fails_with_the_wrong_password(session):
    signup(session, "alice", "correct horse battery")
    with pytest.raises(InvalidCredentialsError):
        login(session, "alice", "wrong password")


def test_login_fails_for_an_unknown_username(session):
    with pytest.raises(InvalidCredentialsError):
        login(session, "nobody", "whatever password")
