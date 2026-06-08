"""Per-account login lockout: unit tests (fake clock) + HTTP integration."""

import pytest

from app.core.errors import TooManyAttemptsError
from app.utils.login_guard.guard import InMemoryLoginGuard


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, secs):
        self.t += secs


def test_locks_after_threshold_then_unlocks():
    clock = _Clock()
    g = InMemoryLoginGuard(max_failures=3, lockout_seconds=60, clock=clock)

    g.assert_not_locked("a@e.com")  # clean
    for _ in range(3):
        g.record_failure("a@e.com")

    with pytest.raises(TooManyAttemptsError):
        g.assert_not_locked("a@e.com")

    clock.advance(61)  # lockout window elapsed
    g.assert_not_locked("a@e.com")  # no longer locked


def test_success_resets_failures():
    clock = _Clock()
    g = InMemoryLoginGuard(max_failures=3, lockout_seconds=60, clock=clock)
    g.record_failure("a@e.com")
    g.record_failure("a@e.com")
    g.record_success("a@e.com")  # clears
    g.record_failure("a@e.com")
    g.assert_not_locked("a@e.com")  # only 1 failure since reset → not locked


def test_lockout_is_per_account_and_case_insensitive():
    g = InMemoryLoginGuard(max_failures=2, lockout_seconds=60)
    g.record_failure("Alice@Example.com")
    g.record_failure("alice@example.com")  # same account, different case
    with pytest.raises(TooManyAttemptsError):
        g.assert_not_locked("ALICE@EXAMPLE.COM")
    g.assert_not_locked("bob@example.com")  # a different account is unaffected


def test_retry_after_header_on_lockout():
    g = InMemoryLoginGuard(max_failures=1, lockout_seconds=120)
    g.record_failure("a@e.com")
    try:
        g.assert_not_locked("a@e.com")
        raise AssertionError("expected lockout")
    except TooManyAttemptsError as exc:
        assert exc.headers["Retry-After"]
        assert exc.details["retry_after_seconds"] <= 120


def test_http_login_lockout_returns_429(client, alice, monkeypatch):
    """After enough failed logins the account is locked (429) even with the
    correct password, until the lockout expires."""
    from app.core.deps import _login_guard

    monkeypatch.setattr(_login_guard, "_max", 3)  # speed up: lock after 3 tries
    _login_guard.clear()

    creds = {"email": "alice@example.com", "password": "wrong"}
    for _ in range(3):
        assert client.post("/api/auth/login", json=creds).status_code == 401

    # Now locked — even the correct password is refused with 429 + Retry-After.
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert r.headers.get("retry-after")
