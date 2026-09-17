import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app


@pytest.fixture()
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_signup_via_api_returns_a_user_id(client):
    resp = client.post("/auth/signup", json={"username": "alice", "password": "correct horse battery"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert body["user_id"]


def test_signup_with_duplicate_username_is_409(client):
    client.post("/auth/signup", json={"username": "alice", "password": "correct horse battery"})
    resp = client.post("/auth/signup", json={"username": "alice", "password": "another password"})
    assert resp.status_code == 409


def test_signup_with_short_password_is_422(client):
    resp = client.post("/auth/signup", json={"username": "bob", "password": "short"})
    assert resp.status_code == 422


def test_login_via_api_returns_the_same_user_id_as_signup(client):
    signup_resp = client.post("/auth/signup", json={"username": "alice", "password": "correct horse battery"})
    login_resp = client.post("/auth/login", json={"username": "alice", "password": "correct horse battery"})
    assert login_resp.status_code == 200
    assert login_resp.json()["user_id"] == signup_resp.json()["user_id"]


def test_login_with_wrong_password_is_401(client):
    client.post("/auth/signup", json={"username": "alice", "password": "correct horse battery"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong password"})
    assert resp.status_code == 401


def test_login_with_unknown_username_is_401(client):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "whatever password"})
    assert resp.status_code == 401
