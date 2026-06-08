"""Authentication: registration, login, and protected-route enforcement."""

from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import get_settings
from app.utils.security.token import JwtTokenProvider
from tests.conftest import TEST_PASSWORD, auth_header, register


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
        json={"username": "alice2", "email": "alice@example.com", "password": TEST_PASSWORD},
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


def test_password_policy_rejects_common_and_similar(client):
    # Common password.
    r = client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    assert r.status_code == 422
    # Password contains the username.
    r = client.post(
        "/api/auth/register",
        json={"username": "daniel", "email": "d@example.com", "password": "daniel-secret"},
    )
    assert r.status_code == 422
    # Too short (<10).
    r = client.post(
        "/api/auth/register",
        json={"username": "erin", "email": "erin@example.com", "password": "Sh0rt!"},
    )
    assert r.status_code == 422


def test_token_has_unique_jti(client):
    from app.config import get_settings
    from app.utils.security.token import JwtTokenProvider

    s = get_settings()
    tp = JwtTokenProvider(secret=s.jwt_secret, algorithm=s.jwt_algorithm, expires_minutes=5)
    import jwt as pyjwt

    claims = pyjwt.decode(tp.create_access_token(1), s.jwt_secret, algorithms=[s.jwt_algorithm])
    assert "jti" in claims and len(claims["jti"]) >= 16


def test_login_success(client):
    register(client)
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": TEST_PASSWORD},
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
