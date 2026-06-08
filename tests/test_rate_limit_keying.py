"""Rate-limit key derivation: per-user keying + proxy-header trust policy."""

import app.core.rate_limit as rl
from app.utils.security.token import JwtTokenProvider


class _FakeRequest:
    def __init__(self, headers=None, client_host="10.0.0.1"):
        self.headers = headers or {}

        class _C:
            host = client_host

        self.client = _C()


def test_anonymous_request_keys_by_ip():
    assert rl.client_key(_FakeRequest(client_host="1.2.3.4")) == "ip:1.2.3.4"


def test_forwarded_for_ignored_unless_trusted(monkeypatch):
    req = _FakeRequest(headers={"x-forwarded-for": "9.9.9.9"}, client_host="1.2.3.4")
    monkeypatch.setattr(rl.settings, "trust_proxy_headers", False)
    assert rl.client_key(req) == "ip:1.2.3.4"  # spoofed XFF ignored
    monkeypatch.setattr(rl.settings, "trust_proxy_headers", True)
    assert rl.client_key(req) == "ip:9.9.9.9"  # trusted → leftmost XFF used


def test_authenticated_request_keys_by_user():
    s = rl.settings
    token = JwtTokenProvider(
        secret=s.jwt_secret, algorithm=s.jwt_algorithm, expires_minutes=5
    ).create_access_token(42)
    req = _FakeRequest(headers={"authorization": f"Bearer {token}"})
    assert rl.client_key(req) == "user:42"


def test_invalid_token_falls_back_to_ip():
    req = _FakeRequest(headers={"authorization": "Bearer not.a.jwt"}, client_host="5.6.7.8")
    assert rl.client_key(req) == "ip:5.6.7.8"
