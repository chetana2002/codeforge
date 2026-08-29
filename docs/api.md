# API Reference

Full interactive schema (every request/response field, generated from the
Pydantic models) is at `/docs` (Swagger UI) and `/openapi.json` on the
running API — this document covers conventions, auth, and endpoint-by-endpoint
purpose, not an exhaustive field-by-field dump that would just drift out of
sync with the generated schema.

## Response envelope

Every response — success or error — has the same shape:

```json
{ "data": { ... } | null, "error": { "code": "...", "message": "...", "details": {} } | null }
```

Exactly one of `data`/`error` is non-null. `error.code` is a stable,
machine-readable string (`PROJECT_NOT_FOUND`, `RATE_LIMITED`,
`VALIDATION_ERROR`, ...) meant to drive UI logic; `error.message` is a
human-readable fallback. `GET /metrics` is the one deliberate exception — it
returns Prometheus's own plain-text exposition format, not JSON, because
that's what Prometheus's scraper expects.

## Pagination

List endpoints share one shape: `?page=1&page_size=20` (`page_size` capped
at 100), returning
`{ items: [...], total, page, page_size, total_pages }`.

## Authentication

Cookie-based (`HttpOnly`), not bearer tokens — see `security.md` for the
full model. `POST /auth/register` and `POST /auth/login` both set an access
token cookie (15 min) and a refresh token cookie (7 day) directly; there's no
separate "then call /login" step. `POST /auth/refresh` rotates both.
Every endpoint below except `/auth/register`, `/auth/login`, `/health`,
`/ready`, and `/metrics` requires a valid access token cookie and returns
`401 UNAUTHENTICATED` without one.

## Idempotency

`POST /projects/{id}/execute` accepts an `Idempotency-Key` header. A retried
request with the same key and the same underlying `(project_id, file_id,
user_id)` returns the *original* execution instead of creating a duplicate
job. The same key reused with a *different* request body is rejected with
`409 IDEMPOTENCY_KEY_CONFLICT` rather than silently executed against the new
input — see `database-design.md` for how the key is scoped and compared.

## Rate limits

`429 RATE_LIMITED` (with a `Retry-After` header and
`details.retry_after_seconds`) on: login (5/min/IP), project creation
(20/min/user), execution (20/min/user). See `security.md` for the fail-open
behavior if Redis itself is unavailable.

## Endpoints

### Auth (`/auth`)
| Method & path | Purpose |
|---|---|
| `POST /auth/register` | Create an account; sets auth cookies |
| `POST /auth/login` | Authenticate; sets auth cookies (rate-limited) |
| `POST /auth/logout` | Revoke the current session |
| `POST /auth/refresh` | Rotate the refresh token, issue a new access token |
| `GET /auth/me` | The current authenticated user |

### Projects (`/projects`)
| Method & path | Purpose |
|---|---|
| `POST /projects` | Create a project (rate-limited) |
| `GET /projects` | List the current user's projects (paginated, `?q=` search) |
| `GET /projects/{id}` | Get one project (owner-scoped — 404, not 403, for someone else's) |
| `PATCH /projects/{id}` | Update name/description/visibility |
| `DELETE /projects/{id}` | Delete a project and everything under it |

### Files (`/projects/{project_id}/files`)
| Method & path | Purpose |
|---|---|
| `GET /projects/{id}/files` | The full file/folder tree for a project |
| `GET /projects/{id}/files/{file_id}` | One file, including its content |
| `POST /projects/{id}/files` | Create a file or folder |
| `PATCH /projects/{id}/files/{file_id}` | Rename, move, or edit content |
| `DELETE /projects/{id}/files/{file_id}` | Delete (folders cascade to their contents) |

### Executions
| Method & path | Purpose |
|---|---|
| `POST /projects/{id}/execute` | Enqueue a run of one file; `202` immediately, body has the `QUEUED` execution (idempotency-key aware, rate-limited) |
| `POST /executions/{id}/cancel` | Cancel a `QUEUED` or `RUNNING` execution — `409` if already terminal |
| `GET /executions/{id}/stream` | Server-Sent Events: current state immediately, then a push on every change until terminal (see `hld.md`) |
| `GET /executions/{id}` | One execution's full detail, including stdout/stderr |
| `GET /executions/stats` | Aggregate counts for the current user (dashboard) |
| `GET /executions` | The current user's executions across every project (paginated) |
| `GET /projects/{id}/executions` | One project's execution history (paginated) |

### Audit log
| Method & path | Purpose |
|---|---|
| `GET /audit-logs` | The current user's own audit trail, newest first (paginated) — see `security.md` for what's recorded |

### Observability
| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness — always `200` if the process is up |
| `GET /ready` | Readiness — checks Postgres and Redis, `degraded` if either is down |
| `GET /metrics` | Prometheus scrape endpoint (plain text, not the JSON envelope) |
