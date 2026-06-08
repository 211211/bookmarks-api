# Bookmarks API — Technical Assessment

> **Role:** Backend Engineer (Take-Home) · **Stack:** Python · FastAPI · SQLAlchemy · SQLite/PostgreSQL
> **Budget:** 100 points · up to 3 days · ~4–6 h coding · zero paid services
> This document stores the brief, the implementation plan, and the **audit checklist** that is
> verified at the end of the build.

---

## 1. The Brief

Build a **Bookmarks API** — a small but complete backend service that lets users save, tag,
search, and manage web bookmarks. Everything runs locally with free, open-source tools.

### Product

A personal bookmarks manager exposed as a RESTful JSON API.

**Core features**
- CRUD for bookmarks (URL, title, description).
- Tag bookmarks with one or more tags.
- Filter & search by tag, title keyword, and date range.

**Users & Auth**
- Simple user registration & login. JWT-based auth.
- Users can only see and manage their own bookmarks.

**Data layer**
- Free database (SQLite / PostgreSQL / MySQL), run locally. No paid cloud DB.
- Proper schema with migrations. At least 3 tables: `users`, `bookmarks`, `tags` (many-to-many).

**API documentation**
- OpenAPI/Swagger spec at `/docs` (and the raw spec at `/openapi.json`).
- All endpoints documented with request/response schemas, status codes, and auth requirements.

**Quality**
- Input validation. Error handling with consistent JSON responses.
- At least 10 tests covering happy paths, edge cases, auth, and OpenAPI contract validation.

---

## 2. Technology Decisions

| Concern              | Choice                                   | Why |
|----------------------|------------------------------------------|-----|
| Web framework        | **FastAPI**                              | Async-ready, first-class OpenAPI/Swagger out of the box, Pydantic validation. |
| ORM                  | **SQLAlchemy 2.0** (typed `Mapped[...]`) | Mature, explicit relationships, raw-SQL escape hatch for the stats endpoint. |
| Migrations           | **Alembic**                              | Versioned, reversible schema migrations. |
| Validation/schemas   | **Pydantic v2**                          | Request/response models, `HttpUrl`/`EmailStr` validation, OpenAPI schema generation. |
| Auth                 | **PyJWT** + **passlib[bcrypt]**          | HS256 signed JWT; bcrypt password **hashing** (never encryption). |
| Database (default)   | **SQLite**                               | Zero setup, built into Python. |
| Database (container) | **PostgreSQL 16** (via Podman)           | Production-like; selected purely by `DATABASE_URL`. |
| Rate limiting (bonus)| **slowapi**                              | Per-client request throttling. |
| Tests                | **pytest** + **jsonschema** + **openapi-spec-validator** | Behaviour tests + OpenAPI contract validation. |
| Container runtime    | **Podman** (`Containerfile` + `podman-compose.yml`) | Daemonless Docker-compatible; provisions API + Postgres. |

**Database portability:** the app runs on SQLite for local dev and PostgreSQL inside Podman
with **no code change** — only `DATABASE_URL` differs. Dialect-specific SQL (month bucketing in
the stats query) is selected at runtime from the active engine dialect.

---

## 3. Project Architecture

```
.
├── app/
│   ├── main.py              # App factory, middleware, exception handlers, router wiring
│   ├── config.py            # Pydantic-settings (env-driven configuration)
│   ├── database.py          # Engine, session factory, declarative Base, FK pragma
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── associations.py  #   bookmark_tags (M2M association table)
│   │   ├── user.py          #   User
│   │   ├── bookmark.py      #   Bookmark
│   │   └── tag.py           #   Tag
│   ├── schemas/             # Pydantic request/response models
│   │   ├── auth.py · bookmark.py · tag.py · stats.py · common.py
│   ├── core/
│   │   ├── security.py      # Password hashing + JWT sign/verify
│   │   ├── deps.py          # get_db, get_current_user (auth dependency)
│   │   ├── errors.py        # Typed app errors + global exception handlers
│   │   └── rate_limit.py    # slowapi limiter (bonus)
│   ├── crud/                # Data-access layer (keeps routes thin, testable)
│   │   ├── users.py · bookmarks.py · tags.py · stats.py (raw SQL)
│   └── routers/             # HTTP layer
│       ├── auth.py · bookmarks.py · stats.py
├── alembic/                 # Migration environment + versions/
├── tests/                   # pytest suite (auth, CRUD, search, stats, errors, OpenAPI)
├── scripts/seed.py          # Sample-data seeder (bonus)
├── Containerfile            # Podman/Docker image build
├── podman-compose.yml       # API + PostgreSQL stack
├── entrypoint.sh            # Runs migrations then starts uvicorn
├── requirements.txt · pyproject.toml · alembic.ini
├── .env.example · .gitignore · Makefile
└── README.md · ASSESSMENT.md
```

**Layering:** `routers` (HTTP) → `crud` (data access) → `models` (ORM). Cross-cutting concerns
(auth, errors, rate limiting, config) live in `core`. This keeps auth middleware cleanly
separated from route logic and the data layer independently testable.

---

## 4. Data Model

```
users                         bookmarks                      tags
─────────────                 ────────────────────           ──────────────
id          PK                id            PK               id        PK
username    UNIQUE, ≤80       url           NOT NULL ≤2048   name      UNIQUE, lowercase, ≤50
email       UNIQUE, ≤255      title         NOT NULL ≤200
password_hash NOT NULL        description   NULL ≤500
created_at  NOT NULL          user_id       FK→users (CASCADE, indexed)
                              created_at    NOT NULL
                              updated_at    NOT NULL (auto)

bookmark_tags  (association, many-to-many)
──────────────────────────────────────────
bookmark_id  FK→bookmarks (CASCADE)  ┐  composite PRIMARY KEY
tag_id       FK→tags (CASCADE)       ┘
```

**Constraints & indexes**
- `users.username`, `users.email` — unique + indexed.
- `bookmarks.user_id` — indexed (ownership filter on every list query).
- `bookmarks.created_at` — indexed (date-range filter + monthly stats).
- `tags.name` — unique + indexed (lowercased, normalized).
- `bookmark_tags` — composite PK `(bookmark_id, tag_id)`; both FKs `ON DELETE CASCADE`.
- Tags are loaded with `selectin` strategy to avoid N+1 when listing bookmarks.

---

## 5. API Surface

| Method | Path                       | Auth | Description |
|--------|----------------------------|:----:|-------------|
| POST   | `/api/auth/register`       |  —   | Create user, return user + JWT (201). |
| POST   | `/api/auth/login`          |  —   | Authenticate, return user + JWT (200). |
| POST   | `/api/bookmarks`           |  ✔   | Create a bookmark with tags (201). |
| GET    | `/api/bookmarks`           |  ✔   | List own bookmarks; filter `tag`,`q`,`from`,`to`; paginate. |
| GET    | `/api/bookmarks/stats`     |  ✔   | Aggregate stats via **raw SQL**. |
| GET    | `/api/bookmarks/{id}`      |  ✔   | Retrieve one owned bookmark. |
| PUT    | `/api/bookmarks/{id}`      |  ✔   | Replace/update an owned bookmark. |
| DELETE | `/api/bookmarks/{id}`      |  ✔   | Delete an owned bookmark (204). |
| GET    | `/health`                  |  —   | Liveness probe. |
| GET    | `/docs`, `/openapi.json`   |  —   | Swagger UI + OpenAPI 3.1 spec. |

**List query parameters:** `tag`, `q` (keyword), `from` / `to` (ISO dates, inclusive),
`page`, `per_page`, `sort` (e.g. `-created_at`), and `cursor` (bonus keyset pagination).

**Consistent error envelope** (every non-2xx response):
```json
{ "error": { "code": "VALIDATION_ERROR",
             "message": "Title is required and must be under 200 characters.",
             "details": { "field": "title", "constraint": "max_length", "limit": 200 } } }
```

---

## 6. Milestones → Scoring Map

| # | Milestone | Deliverable in this build |
|---|-----------|---------------------------|
| 01 | Project setup & data models | `app/models/*`, `alembic/` initial migration, layered structure, indexes/constraints. |
| 02 | Registration & JWT auth | `core/security.py`, `core/deps.py`, `routers/auth.py`. |
| 03 | Bookmark CRUD | `routers/bookmarks.py`, `crud/bookmarks.py`, ownership scoping, M2M tags. |
| 04 | Search, filter & raw SQL | List filters + pagination + `crud/stats.py` raw SQL aggregation. |
| 05 | OpenAPI/Swagger | FastAPI auto-spec + reusable schemas + documented bearer security at `/docs`. |
| 06 | Error handling & validation | `core/errors.py` global handlers, consistent envelope. |
| 07 | Testing + OpenAPI contract | `tests/*` (>10), including response-vs-spec schema validation. |

---

## 7. Bonus Features (implemented if time allows)

- [x] **Rate limiting** — slowapi, stricter limit on auth endpoints (verified: `x-ratelimit-*` headers).
- [x] **Containerization** — `Containerfile` + `podman-compose.yml` (API + PostgreSQL); built & run.
- [x] **Seed script** — `scripts/seed.py` populates realistic sample data (12 + 2 bookmarks, 19 tags).
- [x] **Cursor-based pagination** — keyset pagination via `cursor` param alongside offset paging.

---

## 8. How to Run (summary — full detail in README)

**Local (SQLite):**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m scripts.seed            # optional sample data
uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
```

**Podman (API + PostgreSQL):**
```bash
podman-compose up --build         # http://127.0.0.1:8000/docs
```

**Tests:**
```bash
pytest -q
```

---

## 9. Final Audit Checklist

> `[x]` = verified (suite: **37 passed**; live SQLite + Podman/PostgreSQL smoke-tested).

### Milestone 01 — Project setup & data models
- [x] `User`, `Bookmark`, `Tag` models + `bookmark_tags` association (true M2M). → `app/models/`
- [x] Appropriate column types, lengths, `NOT NULL`/`UNIQUE` constraints.
- [x] Indexes on FK + frequently-filtered columns (`user_id`, `created_at`, `name`, `email`…).
- [x] Clean layered project structure & version-pinned dependencies.
- [x] Alembic migration runs `upgrade head` and `downgrade base` without errors. → `test_migrations.py`

### Milestone 02 — Registration & JWT auth
- [x] Passwords **hashed** with bcrypt (never stored or reversible). → `core/security.py`
- [x] JWT signed (HS256), verified, with `exp`/`iat` claims and expiry handling.
- [x] Auth dependency separated from route logic; protects all bookmark routes. → `core/deps.py`
- [x] Correct status codes (201 register, 200 login, 401 bad creds, 409 duplicate).

### Milestone 03 — Bookmark CRUD
- [x] RESTful verbs/status codes/resource naming.
- [x] Robust input validation with helpful messages (URL, title, description, tags).
- [x] Ownership scoping — a user can never read/modify another user's bookmarks (404, no leak).
- [x] Clean M2M tag handling (get-or-create, normalize, replace on update).

### Milestone 04 — Search, filter & SQL
- [x] Filters: `tag`, `q` keyword, `from`/`to` date range; combinable.
- [x] Pagination with correct total count; no N+1 (joins + `selectin`, single count query).
- [x] `/stats` uses **raw SQL** with `JOIN`, `GROUP BY`, `COUNT`, date bucketing (sqlite + pg).

### Milestone 05 — OpenAPI/Swagger
- [x] Complete, accurate spec served at `/docs` + `/openapi.json` (validated by `openapi-spec-validator`).
- [x] Reusable component schemas (no inline duplication).
- [x] Bearer auth requirement documented; Swagger "Authorize" works. → `test_openapi.py`

### Milestone 06 — Error handling & validation
- [x] Global handlers produce the consistent `{ "error": {...} }` envelope. → `core/errors.py`
- [x] Validation (422), auth (401), forbidden→404, not-found (404), conflict (409),
      rate-limit (429), and 500 all mapped.

### Milestone 07 — Testing
- [x] ≥10 pytest tests (**37 total**): happy paths, edge cases, auth, ownership.
- [x] Tests assert responses conform to the OpenAPI component schemas. → `test_openapi.py`
- [x] Migration-runs-clean test. → `test_migrations.py`
- [x] Full suite passes (`37 passed`).

### Bonus
- [x] Rate limiting · [x] Podman setup · [x] Seed script · [x] Cursor pagination.

### Delivery
- [x] Incremental, milestone-mapped commit history (13 commits).
- [x] README with setup, run, Podman, and API usage instructions.
- [x] Repo initialized and ready to push to GitHub.

---

## 10. Post-Build Adversarial Review

After the suite passed, an adversarial multi-dimension review (security, correctness,
requirements, API contract, tests/ops) was run and each finding independently verified.
Confirmed items were fixed:

- **Security (critical):** the app now refuses to start outside `development` with a weak,
  empty, or well-known default `JWT_SECRET` (prevents token forgery from a committed secret).
- **Security:** switched password hashing to `bcrypt_sha256` (no silent 72-byte truncation);
  the JWT `type` claim is now verified; login does constant-time work for unknown emails
  (no user-enumeration timing side channel).
- **Correctness:** fixed a cursor-pagination off-by-one (`has_next`/`next_cursor` at exact
  page-size multiples) and escaped `LIKE` wildcards (`%`, `_`) in keyword search.
- **API/Docs:** documented the `429` response and clarified cursor/date-range query semantics.
- **Tests:** added expired-token, wrong-token-type, FK-cascade, date/cursor boundary, and a
  migration-drift (`alembic check`) test. Suite: **40 passing**.

---

## 11. Post-Build Enhancements

Beyond the original brief, the following were added (see `README.md` / `TESTING.md`):

- **Repository pattern** — layered `router → service → repository` with an interface per
  model/service/repository/util (`app/repositories`, `app/services`, `app/utils`).
- **Optimistic concurrency (ETag / If-Match)** to prevent lost updates / race conditions:
  bookmarks carry a `version` counter (`bookmarks.version`, migration `0002`); single-bookmark
  responses return a strong `ETag`; `PUT`/`DELETE` require `If-Match` (**428** if missing,
  **412** if stale). Protection is two-layered — an application-level `If-Match` check **and**
  a SQLAlchemy `version_id_col` so the conditional `UPDATE ... WHERE version = <expected>` is
  atomic at the database level (a genuine concurrent commit raises a conflict → 412).
- Test suite expanded to **59 tests** (adds `tests/test_etag.py` + service-layer concurrency tests).
