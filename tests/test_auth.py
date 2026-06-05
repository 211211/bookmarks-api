"""Authentication: registration, login, and protected-route enforcement."""

from tests.conftest import auth_header, register


def test_register_success(client):
    data = register(client)
    assert data["token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    # Password / hash must never be exposed.
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_duplicate_email(client):
    register(client)
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice2", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_register_validation_error(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "al", "email": "not-an-email", "password": "short"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "field" in body["error"]["details"]


def test_login_success(client):
    register(client)
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_wrong_password(client):
    register(client)
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"


def test_protected_route_requires_token(client):
    resp = client.get("/api/bookmarks")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"


def test_protected_route_rejects_garbage_token(client):
    resp = client.get("/api/bookmarks", headers=auth_header("not.a.jwt"))
    assert resp.status_code == 401
