# Testing Guide — Bookmarks API

A step-by-step guide to verifying the API, covering **automated tests** and a full
**manual walkthrough** (Swagger UI and `curl`), plus the **Podman** stack and negative cases.

- Base URL (local & Podman): `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs`
- Every error has the shape `{ "error": { "code", "message", "details" } }`.

---

## 1. Automated tests

### 1.1 Set up

```bash
make install          # create .venv + install dev deps   (or: pip install -r requirements-dev.txt)
source .venv/bin/activate
```

### 1.2 Run

```bash
make test             # run the full pytest suite        → expect: 47 passed
make cov              # tests + coverage report          → expect: ~96% TOTAL
make lint             # ruff                              → expect: All checks passed!
make check            # lint + test together (CI gate)
```

### 1.3 What the suite covers

| File | What it verifies |
|------|------------------|
| `tests/test_auth.py`       | register, login, duplicate (409), bad password (401), missing/garbage/expired/wrong-type token. |
| `tests/test_bookmarks.py`  | CRUD, validation (bad URL, long/missing title), tag normalization, **ownership isolation**. |
| `tests/test_search.py`     | filter by `tag`, keyword `q`, date range (inclusive boundaries), offset + cursor pagination. |
| `tests/test_stats.py`      | raw-SQL stats (totals, top tags, per-month), empty case, per-user scoping. |
| `tests/test_errors.py`     | the consistent error envelope across error types. |
| `tests/test_openapi.py`    | spec validity, Swagger served, bearer scheme documented, responses match component schemas. |
| `tests/test_migrations.py` | migrations `upgrade head` + `downgrade base` run clean, **no model drift** (`alembic check`). |
| `tests/test_cascade.py`    | deleting a user cascades to bookmarks + m2m links. |
| `tests/test_rate_limit.py` | a tripped limit returns `429` in the envelope. |
| `tests/test_services.py`   | **service layer in isolation** against fake repositories (no DB / bcrypt / HTTP). |

---

## 2. Manual testing — set up a running server

Pick **one** of the two options.

### Option A — Local (SQLite)

```bash
source .venv/bin/activate
export DATABASE_URL="sqlite:///./bookmarks.db"
export JWT_SECRET="local-dev-secret-0123456789-abcdefghij-长enough"
alembic upgrade head
python -m scripts.seed          # loads sample data
uvicorn app.main:app --reload
```

### Option B — Podman (PostgreSQL)

```bash
make up                                            # build + start API + PostgreSQL
# wait until healthy, then seed:
podman-compose exec -T api python -m scripts.seed
```

Either way, confirm it's alive:

```bash
curl -s http://127.0.0.1:8000/health
# → {"status":"ok"}
```

**Seeded logins:** `alice@example.com` / `password123` and `bob@example.com` / `password123`.

---

## 3. Manual testing via Swagger UI (no terminal)

1. Open **http://127.0.0.1:8000/docs**.
2. `POST /api/auth/login` → **Try it out** → body `{"email":"alice@example.com","password":"password123"}` → **Execute**. Copy the `token` from the response.
3. Click **Authorize** (top right), paste the token, **Authorize**, **Close**.
4. Now every `/api/bookmarks*` endpoint is callable. Try `GET /api/bookmarks`, `POST /api/bookmarks`, `GET /api/bookmarks/stats`.

---

## 4. Manual testing via `curl` (step by step)

Each step lists the **command** and the **expected result**.

### Step 1 — Health check
```bash
curl -s http://127.0.0.1:8000/health
```
✅ `{"status":"ok"}`

### Step 2 — Register a new user
```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"tester","email":"tester@example.com","password":"password123"}'
```
✅ **201** with `{ "user": {...}, "token": "...", "token_type": "bearer" }`. No password/hash in the response.

### Step 3 — Log in and capture the token
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "$TOKEN"
```
✅ Prints a JWT (three dot-separated segments).

### Step 4 — Auth is required
```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/bookmarks
```
✅ **401** (no token). Error code `AUTHENTICATION_ERROR`.

### Step 5 — Create a bookmark (tags get normalized)
```bash
curl -s -X POST http://127.0.0.1:8000/api/bookmarks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"https://news.ycombinator.com","title":"Hacker News","description":"tech news","tags":["News","Tech","news"]}'
```
✅ **201**. `tags` come back as `["news","tech"]` (lowercased + de-duplicated). Note the returned `id`.

### Step 6 — List your bookmarks
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks" -H "Authorization: Bearer $TOKEN"
```
✅ **200** `{ "items": [...], "pagination": { "total": ..., "page": 1, ... } }`.

### Step 7 — Filter by tag
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks?tag=python" -H "Authorization: Bearer $TOKEN"
```
✅ Only bookmarks tagged `python` (seeded alice has several).

### Step 8 — Keyword search (title + description, case-insensitive)
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks?q=docs" -H "Authorization: Bearer $TOKEN"
```
✅ Matches like "FastAPI docs", "Podman docs", "pytest docs", "PostgreSQL docs".

### Step 9 — Date-range filter (UTC, inclusive)
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks?from=2025-03-01&to=2025-03-31" \
  -H "Authorization: Bearer $TOKEN"
```
✅ Only bookmarks created in March 2025 (seeded alice has 3).

### Step 10 — Offset pagination
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks?page=1&per_page=3" -H "Authorization: Bearer $TOKEN"
```
✅ `items` has ≤3 entries; `pagination` shows `total`, `total_pages`, `has_next`, `has_prev`.

### Step 11 — Cursor (keyset) pagination
```bash
# First page:
curl -s "http://127.0.0.1:8000/api/bookmarks?per_page=3&cursor=999999" -H "Authorization: Bearer $TOKEN"
# Take pagination.next_cursor from the response and request the next page:
curl -s "http://127.0.0.1:8000/api/bookmarks?per_page=3&cursor=<next_cursor>" -H "Authorization: Bearer $TOKEN"
```
✅ Pages don't overlap; the final page returns `next_cursor: null` and `has_next: false`.

### Step 12 — Get one bookmark
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks/1" -H "Authorization: Bearer $TOKEN"
```
✅ **200** with that bookmark (must be owned by you).

### Step 13 — Update a bookmark (partial; replaces tags)
```bash
curl -s -X PUT "http://127.0.0.1:8000/api/bookmarks/1" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Updated Title","tags":["sql","backend"]}'
```
✅ **200**; `title` updated, `tags` now `["backend","sql"]` (sorted), `updated_at` bumped.

### Step 14 — Stats (raw SQL)
```bash
curl -s "http://127.0.0.1:8000/api/bookmarks/stats" -H "Authorization: Bearer $TOKEN"
```
✅ `{ "total_bookmarks", "total_tags", "top_tags":[{name,count}], "bookmarks_per_month":[{month,count}] }`.

### Step 15 — Delete a bookmark
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "http://127.0.0.1:8000/api/bookmarks/1" \
  -H "Authorization: Bearer $TOKEN"
```
✅ **204**. A follow-up `GET /api/bookmarks/1` now returns **404**.

---

## 5. Negative & security cases

### 5.1 Ownership isolation (bob cannot see alice's data)
```bash
BTOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","password":"password123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Bob tries to read one of alice's bookmarks (e.g. id 2):
curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:8000/api/bookmarks/2" \
  -H "Authorization: Bearer $BTOKEN"
```
✅ **404** (not 403) — the API never reveals that another user's bookmark exists.

### 5.2 Validation error (bad URL)
```bash
curl -s -X POST http://127.0.0.1:8000/api/bookmarks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"url":"not-a-url","title":"x"}'
```
✅ **422** `{"error":{"code":"VALIDATION_ERROR","message":"url: ...","details":{"field":"url",...}}}`.

### 5.3 Duplicate registration
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"password123"}'
```
✅ **409** (`CONFLICT`).

### 5.4 Wrong password
```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"wrong"}'
```
✅ **401** (`AUTHENTICATION_ERROR`), generic message (no user enumeration).

### 5.5 Production refuses a weak JWT secret (fail-closed)
```bash
ENVIRONMENT=production JWT_SECRET=short python -c "from app.config import Settings; Settings()"
```
✅ Raises a validation error — the app will not boot with a weak/short secret outside development.

---

## 6. OpenAPI / docs checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs          # → 200 (Swagger UI)
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['openapi'], len(d['paths']),'paths')"
# → 3.1.0  7 paths
```

---

## 7. Tear down

```bash
# Local:
deactivate ; rm -f bookmarks.db

# Podman:
make down            # keep data
make down ARGS=-v    # drop the database volume too
```

---

## Quick checklist

- [ ] `make check` → lint clean + 47 passed
- [ ] `make cov` → ~96%
- [ ] Health, register, login work
- [ ] Auth required (401 without token)
- [ ] Create / list / get / update / delete bookmark
- [ ] Filter by `tag`, search `q`, date range, pagination (offset + cursor)
- [ ] Stats returns totals + top tags + per-month
- [ ] Ownership isolation (cross-user → 404)
- [ ] Validation (422), duplicate (409), wrong password (401)
- [ ] `/docs` + `/openapi.json` reachable
