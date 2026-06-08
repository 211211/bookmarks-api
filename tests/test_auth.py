"""Authentication: registration, login, and protected-route enforcement."""

from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import get_settings
from app.utils.security.token import JwtTokenProvider
from tests.conftest import auth_header, register


def _token_provider() -> JwtTokenProvider:
    s = get_settings()
    return JwtTokenProvider(
        secret=s.jwt_secret, algorithm=s.jwt_algorithm, expires_minutes=s.jwt_expires_minutes
    )


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


def test_expired_token_rejected(client, alice):
    token = _token_provider().create_access_token(alice["user"]["id"], expires_minutes=-1)
    resp = client.get("/api/bookmarks", headers=auth_header(token))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"


def test_wrong_token_type_rejected(client, alice):
    """A correctly-signed but non-'access' token must be rejected."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(alice["user"]["id"]),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "type": "refresh",
    }
    token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    resp = client.get("/api/bookmarks", headers=auth_header(token))
    assert resp.status_code == 401
