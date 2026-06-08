"""Rate limiting (bonus) built on slowapi.

A global default limit applies to every request; auth endpoints get a stricter
limit (see routers/auth.py). Disable entirely with ``RATE_LIMIT_ENABLED=false``.
"""

from __future__ import annotations

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.utils.security.token import JwtTokenProvider

settings = get_settings()

# Used only to read the `sub` claim for per-user rate-limit keying (best-effort).
_token_provider = JwtTokenProvider(
    secret=settings.jwt_secret,
    algorithm=settings.jwt_algorithm,
    expires_minutes=settings.jwt_expires_minutes,
)


def _client_ip(request: Request) -> str:
    """Resolve the client IP. Only honour X-Forwarded-For when explicitly
    configured to trust the proxy — otherwise it is attacker-spoofable."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def client_key(request: Request) -> str:
    """Rate-limit key: prefer the authenticated user (stable across IPs / shared
    NAT), falling back to the (proxy-aware) client IP for anonymous requests."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            sub = _token_provider.decode(auth[7:]).get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.InvalidTokenError:
            pass  # invalid/expired token → fall back to IP keying
    return f"ip:{_client_ip(request)}"


# `storage_uri` (e.g. redis://...) makes limits correct across workers/replicas;
# defaults to in-process memory which is fine for a single worker / local dev.
_limiter_kwargs = {
    "key_func": client_key,
    "default_limits": [settings.rate_limit_default],
    "enabled": settings.rate_limit_enabled,
    "headers_enabled": True,
}
if settings.rate_limit_storage_uri:
    _limiter_kwargs["storage_uri"] = settings.rate_limit_storage_uri

limiter = Limiter(**_limiter_kwargs)


def rate_limit_exceeded_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Render slowapi's limit error in the project's consistent envelope."""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Rate limit exceeded. Please slow down and try again shortly.",
                "details": {"limit": str(exc.limit.limit)},
            }
        },
    )
