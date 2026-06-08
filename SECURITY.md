# Security & Hardening

This document records the threat model, the hardening that is implemented, and the
improvements deliberately deferred (with the reasoning) for this Bookmarks API.

## Threat model (summary)

A multi-tenant JSON API where each user manages their own bookmarks. Primary risks:
credential attacks (brute force / stuffing), token theft, cross-tenant data access,
injection, and resource-exhaustion (DoS). TLS termination and a reverse proxy are assumed
to sit in front of the app in production.

## Implemented controls

### Authentication & accounts
- Passwords **hashed** with `bcrypt_sha256` (full password used; no 72-byte truncation).
- **Password policy**: ≥10 chars, rejects common passwords and values similar to the
  username/email (`app/schemas/auth.py`).
- **JWT** HS256 with `sub`/`iat`/`exp`/`type`/`jti`; `type` is verified; `jti` is present so a
  revocation deny-list can be added without a token-format change.
- **Fail-closed secret**: outside `development` the app refuses to start with a weak/short/
  well-known `JWT_SECRET` (`app/config.py`).
- **Constant-time login** for unknown emails (dummy-hash verify) — no user enumeration via timing.
- **Per-account lockout**: after `LOGIN_MAX_FAILURES` failures an account is locked for
  `LOGIN_LOCKOUT_SECONDS` and returns **429** + `Retry-After`, independent of source IP
  (`app/utils/login_guard/`).

### Authorization
- Every bookmark query is scoped by `user_id`; cross-tenant access returns **404** (never
  reveals existence). Ownership is checked before any precondition.

### Concurrency / integrity
- Optimistic concurrency (`ETag` / `If-Match`, `version` column + SQLAlchemy `version_id_col`):
  prevents lost updates; conflicts return **412**, missing precondition **428**.

### HTTP / transport
- **Security headers** on every response: `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`, a locked-down `Content-Security-Policy`;
  optional **HSTS** (`HSTS_ENABLED`, enable behind TLS).
- **Configurable CORS** allow-list (`CORS_ORIGINS`) — no hardcoded wildcard in production.
- **TrustedHostMiddleware** when `TRUSTED_HOSTS` is set (mitigates Host-header attacks).
- **Request body size limit** (`MAX_REQUEST_BYTES`, default 1 MiB) → **413**.
- **Request IDs** (`X-Request-ID`, generated or echoed) for log correlation.
- Interactive **docs can be disabled** in production (`DOCS_ENABLED=false`).

### Abuse / DoS
- Rate limiting (slowapi): per-authenticated-user keying when a token is present, else per-IP.
- **Proxy-aware IP**: `X-Forwarded-For` is only trusted when `TRUST_PROXY_HEADERS=true`
  (otherwise it is attacker-spoofable).
- Optional **shared limiter store** (`RATE_LIMIT_STORAGE_URI`, e.g. Redis) for correct limits
  across multiple workers/replicas.
- Pagination is capped (`per_page` ≤ 100).

### Data / DB
- Raw SQL is fully parameterized; LIKE wildcards in search are escaped.
- `url` column sized (2083) to match validated `HttpUrl` max — no truncation/`500` on PostgreSQL.
- Composite index `(user_id, created_at)` for the list+sort access pattern.
- Connection-pool tuning (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`,
  `DB_POOL_TIMEOUT`) for client/server databases.

### Ops / supply-chain
- Container runs as a **non-root** user with `cap_drop: ALL` and `no-new-privileges`; image and
  service **HEALTHCHECK**s; readiness probe (`/health/ready`) verifies DB connectivity.
- **CI** (`.github/workflows/ci.yml`): ruff + pytest on every push/PR, plus a non-blocking
  **pip-audit** dependency vulnerability scan (`make audit` locally).

## Deferred (with reasoning)

These are sensible next steps but out of scope for a take-home and/or need extra infrastructure:

| Item | Why deferred | Path to add |
|------|--------------|-------------|
| Refresh tokens + short-lived access tokens, logout endpoint | Larger auth surface; needs token storage | Issue short access + rotating refresh; add `/auth/logout` |
| Full token revocation (deny-list / `token_version`) | No password-change/logout flow to trigger it yet; `jti` already emitted | Add `tokens_valid_after`/`token_version` on `User`, gate in `get_current_user` |
| JWT key rotation (`kid`) / asymmetric (RS256) | Single-service deployment; HS256 is adequate | Add `kid` header + key map; move to RS256 for multi-service |
| Redis-backed rate limiting by default | Needs Redis; in-memory is fine for single worker | Set `RATE_LIMIT_STORAGE_URI` |
| Metrics/tracing (Prometheus/OTel) | Observability beyond logs/health | Add `/metrics` + OTel middleware |
| Breached-password check (HIBP k-anonymity) | External call; small denylist covers the obvious | Add an async HIBP range lookup at register |
| Per-request handler timeout (slowloris) | Better handled at the proxy/uvicorn layer | `--timeout-keep-alive` + proxy timeouts |
| Migration advisory lock on multi-replica deploy | Single-instance demo; entrypoint runs migrations once | Wrap `alembic upgrade` in a Postgres advisory lock |
| Pinned/hashed dependency lockfile | Ranges + CI pip-audit cover most of the risk | `pip-compile --generate-hashes` → `requirements.lock` |
| Read-only container root FS | Avoids breakage risk; bytecode writes already disabled | Add `read_only: true` + tmpfs for `/tmp` |

## Reporting

For a real deployment, report vulnerabilities privately to the maintainer rather than via a
public issue.
