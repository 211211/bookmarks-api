# Bookmarks API

A small but complete RESTful JSON API to **save, tag, search, and manage** web bookmarks.
Built with **FastAPI**, **SQLAlchemy 2.0**, and **Alembic**, with JWT authentication,
consistent error handling, an auto-generated OpenAPI/Swagger spec, and a full test suite.

> Runs locally on **SQLite** with zero setup, or on **PostgreSQL** via **Podman** with no code
> change — only `DATABASE_URL` differs.

---

## Features

- **Auth** — register & log in; JWT (HS256) bearer tokens; bcrypt-hashed passwords.
- **Bookmarks** — full CRUD, every record scoped to its owner (no cross-user leaks).
- **Tags** — many-to-many; normalized (lowercased, de-duplicated); get-or-create.
- **Search & filter** — by `tag`, keyword `q` (title/description), and `from`/`to` date range.
- **Pagination** — offset pagination with total count **and** bonus keyset/cursor pagination.
- **Stats** — aggregate counts via **raw SQL** (`JOIN` / `GROUP BY` / `COUNT` / month bucketing).
- **OpenAPI 3.1** — interactive docs at `/docs`, raw spec at `/openapi.json`.
- **Consistent errors** — every failure returns `{ "error": { "code", "message", "details" } }`.
- **Bonus** — rate limiting, Podman containerization, seed script, cursor pagination.

---

## Tech stack

| Layer        | Choice                                              |
|--------------|-----------------------------------------------------|
| Framework    | FastAPI + Uvicorn                                    |
| ORM          | SQLAlchemy 2.0 (typed models)                       |
| Migrations   | Alembic                                              |
| Validation   | Pydantic v2 (`HttpUrl`, `EmailStr`)                 |
| Auth         | PyJWT + passlib[bcrypt]                              |
| Rate limit   | slowapi                                             |
| Database     | SQLite (default) / PostgreSQL (Podman)              |
| Tests        | pytest + jsonschema + openapi-spec-validator        |
| Container    | Podman (`Containerfile` + `podman-compose.yml`)     |

---

## Quick start (local, SQLite)

Requires **Python 3.10+**.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Configure (optional — sensible defaults work out of the box)
cp .env.example .env

# 4. Create the database schema
alembic upgrade head

# 5. (Optional) load sample data
python -m scripts.seed

# 6. Run the server
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive Swagger UI.

Seeded logins (after step 5): `alice@example.com` / `password123` and `bob@example.com` / `password123`.

---

## Run with Podman (API + PostgreSQL)

Requires **Podman** and **podman-compose** (a running `podman machine` on macOS/Windows).

```bash
podman-compose up --build
```

This starts PostgreSQL, waits for it to become healthy, applies migrations, and serves the API
at **http://127.0.0.1:8000/docs**. Tear down with `podman-compose down` (add `-v` to drop data).

> Docker users can substitute `docker compose -f podman-compose.yml up --build`.

---

## Configuration

All settings come from environment variables (or `.env`). See [`.env.example`](.env.example).

| Variable               | Default                          | Description |
|------------------------|----------------------------------|-------------|
| `DATABASE_URL`         | `sqlite:///./bookmarks.db`       | SQLAlchemy URL. Use `postgresql+psycopg://…` for Postgres. |
| `JWT_SECRET`           | dev placeholder                  | **Change in production.** Signing key. |
| `JWT_ALGORITHM`        | `HS256`                          | JWT algorithm. |
| `JWT_EXPIRES_MINUTES`  | `1440`                           | Token lifetime. |
| `RATE_LIMIT_ENABLED`   | `true`                           | Toggle rate limiting. |
| `RATE_LIMIT_DEFAULT`   | `120/minute`                     | Global per-client limit. |
| `RATE_LIMIT_AUTH`      | `15/minute`                      | Stricter limit on auth routes. |

---

## API reference

Base URL: `http://127.0.0.1:8000`. All `/api/bookmarks*` routes require
`Authorization: Bearer <token>`.

| Method | Path                     | Auth | Description |
|--------|--------------------------|:----:|-------------|
| POST   | `/api/auth/register`     |  —   | Create user → `{ user, token }` (201). |
| POST   | `/api/auth/login`        |  —   | Authenticate → `{ user, token }` (200). |
| POST   | `/api/bookmarks`         |  ✔   | Create a bookmark (201). |
| GET    | `/api/bookmarks`         |  ✔   | List/search/filter/paginate own bookmarks. |
| GET    | `/api/bookmarks/stats`   |  ✔   | Aggregate stats (raw SQL). |
| GET    | `/api/bookmarks/{id}`    |  ✔   | Get one owned bookmark. |
| PUT    | `/api/bookmarks/{id}`    |  ✔   | Update an owned bookmark. |
| DELETE | `/api/bookmarks/{id}`    |  ✔   | Delete an owned bookmark (204). |
| GET    | `/health`                |  —   | Liveness probe. |
| GET    | `/docs`, `/openapi.json` |  —   | Swagger UI + OpenAPI spec. |

### List query parameters

| Param      | Example          | Description |
|------------|------------------|-------------|
| `tag`      | `python`         | Filter by exact tag. |
| `q`        | `fastapi`        | Keyword in title/description (case-insensitive). |
| `from`     | `2025-01-01`     | Created on/after (inclusive). |
| `to`       | `2025-12-31`     | Created on/before (inclusive). |
| `page`     | `1`              | 1-based page (offset pagination). |
| `per_page` | `20`             | Items per page (max 100). |
| `sort`     | `-created_at`    | `created_at`/`updated_at`/`title`/`id`; `-` = descending. |
| `cursor`   | `123`            | Keyset cursor (bonus). |

### Example session

```bash
# Register
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"password123"}'

# Save the token, then create a bookmark
TOKEN="<token from above>"
curl -s -X POST http://127.0.0.1:8000/api/bookmarks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"https://fastapi.tiangolo.com","title":"FastAPI","tags":["python","backend"]}'

# Search
curl -s "http://127.0.0.1:8000/api/bookmarks?tag=python&q=fast&page=1&per_page=10" \
  -H "Authorization: Bearer $TOKEN"

# Stats
curl -s http://127.0.0.1:8000/api/bookmarks/stats -H "Authorization: Bearer $TOKEN"
```

### Error shape

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "title: String should have at most 200 characters",
    "details": { "field": "title", "constraint": "string_too_long", "limit": 200 }
  }
}
```

---

## Data model

```
users ──< bookmarks >──< bookmark_tags >──< tags
```

- `users` — `id`, `username` (unique), `email` (unique), `password_hash`, `created_at`.
- `bookmarks` — `id`, `url`, `title`, `description?`, `user_id` (FK, cascade), `created_at`, `updated_at`.
- `tags` — `id`, `name` (unique, lowercase).
- `bookmark_tags` — composite PK `(bookmark_id, tag_id)`, both FKs cascade.

Indexes on `users.username/email`, `tags.name`, `bookmarks.user_id`, and `bookmarks.created_at`.

---

## Testing

```bash
pytest            # or: make test
```

The suite (>20 tests) covers registration/login, JWT enforcement, CRUD, **ownership
isolation**, search/filter/pagination (offset + cursor), the raw-SQL stats endpoint, the
consistent error envelope, that **migrations run clean**, and **OpenAPI contract validation**
(real responses are validated against the advertised component schemas).

---

## Architecture (repository pattern)

Each request flows through clean layers, each depending on the *interface* of the one below:

```
HTTP router  →  service (business logic)  →  repository (persistence)  →  ORM model
                         ↘ utils (password hasher, token provider, tag normalizer)
```

Every model/service/repository/util has a dedicated `interface.py` (an abstract base class)
and an implementation, so services are decoupled from persistence and unit-testable with fakes
(see `tests/test_services.py` — no DB, no bcrypt). Dependency injection is wired in
`app/core/deps.py`.

## Project structure

```
app/
  main.py                 # app factory, middleware, exception handlers
  config.py               # env-driven settings
  database.py             # engine, session, Base
  models/                 # User, Bookmark, Tag, bookmark_tags (ORM)
  schemas/                # Pydantic request/response models
  core/                   # deps (DI wiring), errors, rate limiting
  utils/
    security/             # interface.py + password.py (bcrypt) + token.py (JWT)
    tags/                 # interface.py + normalizer.py
  repositories/
    user/                 # interface.py (IUserRepository) + repository.py
    bookmark/             #   ...one subpackage per entity...
    tag/  ·  stats/
  services/
    auth/                 # interface.py (IAuthService) + service.py
    bookmark/  ·  stats/
  routers/                # auth, bookmarks, stats (depend on service interfaces)
alembic/                  # migration environment + versions
tests/                    # pytest suite (incl. service unit tests with fakes)
scripts/seed.py           # sample-data seeder
Containerfile · podman-compose.yml · entrypoint.sh
```

---

## Notes & trade-offs

- **Ownership scoping** returns `404` (not `403`) for another user's bookmark so the API never
  reveals that the resource exists.
- **Tag normalization** happens at the schema boundary; tags are stored once and shared.
- **Stats** uses raw SQL with a dialect-aware month expression (`strftime` on SQLite,
  `to_char` on PostgreSQL).
- **N+1** is avoided by `selectin` loading of tags and `JOIN`-based filtering with a single
  count query.

## License

MIT — see [LICENSE](LICENSE).
