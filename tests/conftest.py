"""Shared pytest fixtures.

Configure the environment *before* importing the app so that settings, the
engine, and the rate limiter pick up test values. Each test runs against a fresh
in-memory SQLite database (shared across connections via StaticPool).
"""

from __future__ import annotations

import os

# Must be set before `app` is imported (settings are read once at import).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only-0123456789abcdef"
# Keep rate limiting ON (so the slowapi integration path is exercised) but with
# limits high enough that the suite never trips them.
os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["RATE_LIMIT_DEFAULT"] = "100000/minute"
os.environ["RATE_LIMIT_AUTH"] = "100000/minute"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (register models on Base.metadata)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# A single in-memory database shared across all connections in the test process.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Create a clean schema for every test, then drop it."""
    Base.metadata.create_all(bind=test_engine)
    # Reset the process-wide login-guard singleton so lockout state doesn't leak
    # between tests.
    from app.core.deps import _login_guard

    _login_guard.clear()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# ── Helpers ────────────────────────────────────────────────────────────────

def register(client, username="alice", email="alice@example.com", password="password123"):
    """Register a user and return the parsed JSON response."""
    resp = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice(client):
    """A registered user with auth headers ready to use."""
    data = register(client)
    return {"user": data["user"], "token": data["token"], "headers": auth_header(data["token"])}


@pytest.fixture
def bob(client):
    data = register(client, username="bob", email="bob@example.com", password="password456")
    return {"user": data["user"], "token": data["token"], "headers": auth_header(data["token"])}
