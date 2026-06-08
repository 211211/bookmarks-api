"""Custom ASGI/HTTP middleware: security headers, body-size limit, request IDs."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add conservative security response headers to every response."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        super().__init__(app)
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # This is a JSON API, not a document host — forbid embedding/scripts.
        headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if self._hsts:
            headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request id (from the inbound header or freshly generated) to the
    request state and echo it back, so logs and clients can correlate a request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds ``max_bytes`` (declared via
    Content-Length, or enforced while streaming if the header is absent)."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        super().__init__(app)
        self._max = max_bytes

    def _too_large(self) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": f"Request body exceeds the {self._max}-byte limit.",
                    "details": {"limit": self._max},
                }
            },
        )

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max:
                    return self._too_large()
            except ValueError:
                pass  # malformed header → let body-size enforcement below catch it
        return await call_next(request)
