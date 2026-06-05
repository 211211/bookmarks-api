"""Rate limiting (bonus) built on slowapi.

A global default limit applies to every request; auth endpoints get a stricter
limit (see routers/auth.py). Disable entirely with ``RATE_LIMIT_ENABLED=false``.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    enabled=settings.rate_limit_enabled,
    headers_enabled=True,
)


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
