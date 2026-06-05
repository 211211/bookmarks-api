"""FastAPI application factory: middleware, exception handlers, and routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.config import get_settings
from app.core.errors import register_exception_handlers
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
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        contact={"name": "Bookmarks API"},
        license_info={"name": "MIT"},
    )

    # ── Rate limiting (bonus) ──────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS (open in dev; tighten origins for production) ─────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
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
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    @app.get("/health", tags=["health"], summary="Liveness probe")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
