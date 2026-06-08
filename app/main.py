"""FastAPI application factory: middleware, exception handlers, and routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.middleware import (
    MaxBodySizeMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import auth, bookmarks, stats

settings = get_settings()

DESCRIPTION = """
A RESTful JSON API to **save, tag, search, and manage** web bookmarks.

* **Auth** — register & log in to receive a JWT; send it as `Authorization: Bearer <token>`.
* **Bookmarks** — full CRUD, scoped so you only ever see your own.
* **Search** — filter by `tag`, keyword `q`, and `from`/`to` date range, with pagination.
* **Stats** — aggregate counts computed with raw SQL.

Every error follows a single envelope: `{ "error": { "code", "message", "details" } }`.
"""

OPENAPI_TAGS = [
    {"name": "auth", "description": "User registration and login (JWT)."},
    {"name": "bookmarks", "description": "Create, read, update, delete, search, and stats."},
    {"name": "health", "description": "Service liveness."},
]


def create_app() -> FastAPI:
    # Interactive docs can be disabled (e.g. in production) via DOCS_ENABLED.
    docs_kwargs = (
        {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}
        if settings.docs_enabled
        else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    )
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        contact={"name": "Bookmarks API"},
        license_info={"name": "MIT"},
        **docs_kwargs,
    )

    # ── Rate limiting (bonus) ──────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── HTTP hardening ─────────────────────────────────────────────────────
    # NOTE: Starlette runs middleware in reverse registration order, so register
    # these before CORS/rate-limit-sensitive ones as appropriate.
    if settings.security_headers_enabled:
        app.add_middleware(SecurityHeadersMiddleware, hsts=settings.hsts_enabled)
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestIDMiddleware)

    # Reject requests with an untrusted Host header (mitigates host-header attacks).
    if settings.trusted_host_list != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

    # ── CORS (configurable allow-list; defaults to any origin in dev) ──────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Consistent error envelope ──────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routes (stats before bookmarks so /stats isn't read as an id) ──────
    app.include_router(auth.router)
    app.include_router(stats.router)
    app.include_router(bookmarks.router)

    @app.get("/", tags=["health"], summary="Service metadata")
    def root() -> dict:
        return {
            "service": settings.app_name,
            "version": __version__,
            "docs": "/docs" if settings.docs_enabled else None,
            "openapi": "/openapi.json" if settings.docs_enabled else None,
        }

    @app.get("/health", tags=["health"], summary="Liveness probe")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
