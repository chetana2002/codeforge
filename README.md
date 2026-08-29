# CodeForge

**Cloud IDE & Code Execution Platform** — a browser-based code editor with isolated,
sandboxed code execution. Built as a portfolio-grade demonstration of production
software engineering: clean architecture, async job processing, database design,
observability, and security — not a toy CRUD app.

> **Status:** under active, incremental construction. This README tracks what is
> actually implemented and runnable today — see the [Build status](#build-status)
> checklist. Nothing below is claimed to work unless it has been run and verified.

## Architecture

```
                    ┌────────────────────┐
                    │      Browser       │
                    │ Next.js + Monaco   │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │   FastAPI (API)    │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼─────────────────┐
             │                │                  │
             ▼                ▼                  ▼
       PostgreSQL           Redis            (execution
       (metadata)      (cache + streams)      history)
                              │
                              ▼
                     Redis Streams (jobs)
                              │
                              ▼
                     Execution Worker
                              │
                              ▼
                   Docker Sandbox Container
```

The API never executes user code directly. It submits execution jobs onto a Redis
Stream; a separate worker process consumes jobs and runs untrusted code inside
locked-down, ephemeral Docker containers. See [docs/architecture.md](docs/architecture.md)
for the full write-up.

## Documentation

| Doc | Covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System diagram, request paths, why not microservices |
| [docs/hld.md](docs/hld.md) | Component responsibilities, core flows, design principles |
| [docs/lld.md](docs/lld.md) | Request-level detail: SSE mechanics, file-tree algorithms, frontend cache architecture |
| [docs/database-design.md](docs/database-design.md) | Schema, indexes, cascade strategy, migrations |
| [docs/execution-engine.md](docs/execution-engine.md) | State machine, queue delivery semantics, sandbox internals |
| [docs/security.md](docs/security.md) | Auth, authorization, path-traversal prevention, headers, secrets, known limitations |
| [docs/failure-scenarios.md](docs/failure-scenarios.md) | What happens when Postgres/Redis/the worker goes down |
| [docs/scalability.md](docs/scalability.md) | What scales as-is, what becomes the bottleneck, what would need building |
| [docs/observability.md](docs/observability.md) | Health checks, every metric and where it's recorded, dashboards, logging |
| [docs/deployment.md](docs/deployment.md) | Local dev, why migrations aren't automatic, whether this runs on Vercel |
| [docs/tradeoffs.md](docs/tradeoffs.md) | Every major architectural choice, argued against its real alternative |
| [docs/api.md](docs/api.md) | Response envelope, auth, idempotency, rate limits, endpoint reference |

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS, TanStack Query, Zod, React Hook Form, Monaco Editor |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 (Redis Streams for the execution job queue) |
| Execution | Docker-based isolated sandbox containers, run by a dedicated worker |
| Observability | Prometheus, Grafana, structured JSON logging (structlog), OpenTelemetry |
| Testing | pytest, Playwright |
| CI | GitHub Actions |

## Repository layout

```
codeforge/
├── frontend/     Next.js app (App Router)
├── backend/      FastAPI application (clean-architecture layers)
├── worker/       Redis Streams consumer + Docker sandbox execution engine
├── infra/        Prometheus / Grafana provisioning
├── docs/         System design docs (HLD, LLD, security, scalability, tradeoffs...)
├── tests/        Cross-service integration / E2E tests
├── docker-compose.yml
├── .env.example
└── README.md
```

## Local development

### Prerequisites

- Docker + Docker Compose v2
- Node.js 22+ (only needed if you want to run the frontend outside Docker)
- Python 3.12+ (only needed if you want to run the backend/worker outside Docker)

### Environment variables

```bash
cp .env.example .env
```

Edit `.env` as needed — the defaults work out of the box for local development.
**Never commit `.env`.**

### Start everything

```bash
docker compose up --build
```

This starts: `postgres`, `redis`, `api` (FastAPI), `worker`, `frontend` (Next.js),
`prometheus`, `grafana`.

> **Ports:** the default host ports (`API_PORT_HOST`, `FRONTEND_PORT_HOST`,
> `POSTGRES_PORT_HOST`, `REDIS_PORT_HOST`, `PROMETHEUS_PORT_HOST`,
> `GRAFANA_PORT_HOST` in `.env.example`) are deliberately shifted off the usual
> defaults (8001/3002/5435/6381/9091/3003) to avoid clashing with other local
> projects. Override them in `.env` if these are free on your machine and you'd
> rather use the defaults.

- Frontend: http://localhost:3002
- API: http://localhost:8001 — interactive docs at http://localhost:8001/docs
- Health check: http://localhost:8001/health
- Readiness check: http://localhost:8001/ready
- Grafana: http://localhost:3003 (anonymous viewer access enabled for local dev)
- Prometheus: http://localhost:9091

### Database migrations

Migrations are managed with Alembic. The `api` container does **not** run
migrations automatically — apply them explicitly:

```bash
cd backend
alembic upgrade head
```

### Seed data

Optional — a fresh database is a perfectly empty, working app. To have
something to look at immediately instead of registering by hand:

```bash
docker compose exec api python -m app.seed
```

Creates one demo account (`demo@codeforge.dev` / `demo-password-123`) with
two projects (a Python Fibonacci example, a JavaScript prime-finder example),
ready to run. Safe to re-run — it's a no-op if the demo account already
exists.

### Running tests

```bash
# Backend
cd backend
python -m venv .venv && ./.venv/Scripts/pip install -r requirements-dev.txt
pytest -v --cov=app

# Worker
cd worker
python -m venv .venv && ./.venv/Scripts/pip install -r requirements-dev.txt
pytest -v

# Frontend
cd frontend
npm install   # see note in frontend/Dockerfile — `npm ci` hits a known npm 11 /
              # eslint 9 lockfile-consistency bug on this project
npm run lint
npx tsc --noEmit
npm run build
```

### Linting & type-checking

```bash
# Backend / worker
ruff check .
black --check .
mypy app          # backend only

# Frontend
npm run lint
npx tsc --noEmit
```

## Build status

Tracking progress against the phased implementation plan.

- [x] **Phase 1** — Repository structure, Docker Compose, PostgreSQL, Redis, minimal FastAPI (`/health`, `/ready`), minimal Next.js app
- [x] **Phase 2** — Authentication: register/login/logout/refresh/me, bcrypt password hashing, JWT access + rotating refresh-token sessions (HTTP-only cookies), Alembic migration for `users`/`sessions`
- [x] **Phase 3** — Project CRUD (create/list/get/update/delete), owner-scoped access (cross-user access returns 404), pagination, name/description search
- [x] **Phase 4** — File/folder tree (adjacency-list model), create/rename/move/delete, sibling-name conflict detection (409), traversal-proof single-segment name validation, cycle-safe folder moves, cascade delete
- [x] **Phase 5** — Full frontend: auth pages, dashboard, project management UI, file tree, Monaco editor with tabs/save/Ctrl+S, dark/light/system theme, shadcn/ui
- [x] **Phase 6** — Execution data model: `executions`/`execution_logs`/`idempotency_keys` tables, QUEUED→RUNNING→{SUCCESS,FAILED,TIMEOUT,CANCELLED} state machine with an audit-logged `ExecutionService.transition`, read endpoints (`GET /executions/{id}`, `GET /projects/{id}/executions`)
- [x] **Phase 7** — Redis Streams job queue: `POST /projects/{id}/execute` (idempotency-key aware, publishes to `codeforge:executions` via XADD) and `POST /executions/{id}/cancel`
- [x] **Phase 8+9** — Execution worker + Docker sandbox: Redis Streams consumer with at-least-once delivery and XAUTOCLAIM-based retry, `ExecutionRuntime` abstraction (Python/Node), and a locked-down sandbox (no network, CPU/memory/PID limits, non-root, read-only rootfs + tmpfs scratch dir, auto-removed) — proven end-to-end with real container-execution tests (success/failure/timeout/network-block/fork-bomb-block/read-only-enforcement/cleanup) and live pipeline runs
- [x] **Phase 10** — Execution UI: Run button (save-then-execute), polling-based live status in the IDE terminal panel, dashboard wired to real execution stats/recent-executions endpoints
- [x] **Phase 11** — Execution history page (per project, paginated) with a detail dialog showing full stdout/stderr — verified end-to-end in the browser against the live pipeline
- [x] **Phase 12** — SSE execution updates: `GET /executions/{id}/stream` (initial state + Redis pub/sub-driven push until terminal or a max-duration cutoff), frontend `useExecutionStream` (EventSource) writing straight into the execution's query cache, polling kept as a fallback — verified end-to-end in the browser (Run → live "Running…" → stdout/exit code, no manual refresh) and via 90 passing backend tests
- [x] **Phase 13** — Rate limiting: Redis fixed-window limiter (login 5/min/IP, execution + project creation 20/min/user), 429 responses with `RATE_LIMITED` and a `Retry-After` header, fails open on Redis errors — verified live against the running API (20 succeed, 21st 429) and via 4 new backend tests
- [x] **Phase 14** — Observability: `/metrics` on both API (port 8000) and worker (port 9100) — `http_requests_total`/`http_request_duration_seconds` via a raw-ASGI middleware (chosen over `BaseHTTPMiddleware` to avoid interfering with the SSE stream), `execution_total`, `queue_depth` (live `XLEN`), `database_connection_errors`, `rate_limit_rejections_total`, `worker_jobs_total`/`worker_job_failures_total`, `execution_success_total`/`execution_failure_total`, `execution_duration_seconds`; Prometheus scraping both targets; a provisioned Grafana dashboard (`CodeForge Overview`, pinned datasource UID) — all verified live with real traffic, screenshotted rendering real data
- [x] **Phase 15** — Audit logging: `audit_logs` table (no FK on `resource_id` by design — the referenced row can be legitimately gone, e.g. `PROJECT_DELETED`), all 9 event types (login/logout, project/file created/deleted, execution started/completed/cancelled) recorded atomically alongside the action they document, `GET /audit-logs` (paginated, scoped to the requesting user) — verified via 5 new backend tests and live against the real stack, including the worker-side execution_started/execution_completed events
- [x] **Phase 16** — Testing: Playwright E2E covering the full golden path (register → create project → create file → write code → run → see live output → check history) against the real docker-compose stack — hit and fixed a real Monaco/Playwright quirk (`keyboard.type()`'s per-keystroke input fights Monaco's auto-closing brackets/quotes and corrupts the code; fixed with `insertText`); Vitest unit tests for `error-messages.ts` and `api-client.ts` (9 tests) — on top of the existing 99 backend + 13 worker tests
- [x] **Phase 17** — CI: backend (Postgres+Redis services, ruff/black/mypy/pytest), worker (ruff/black/mypy/pytest against real sandbox containers), frontend (lint/typegen/type-check/vitest/build), Docker image builds, and a full end-to-end job that brings up the real docker-compose stack and runs the Playwright golden path — verified on a real GitHub Actions run (not just written): [github.com/chetana2002/codeforge](https://github.com/chetana2002/codeforge), all 5 jobs green after fixing 2 real CI-only failures (Next.js route types not generated on a fresh checkout; worker's sandbox test images not pre-pulled)
- [x] **Phase 18** — Documentation: all 12 docs written (architecture, HLD, LLD, database design, execution engine, security, failure scenarios, scalability, observability, deployment, tradeoffs, API reference) — plus a real gap the writing surfaced and fixed along the way: security-response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, environment-gated HSTS) were an explicit spec requirement that had never actually been implemented; added `SecurityHeadersMiddleware`, tested, and verified live
- [x] **Phase 19** — Production hardening: seed data command (`python -m app.seed`, idempotent, verified live end-to-end including login and reading the seeded projects back through the real API), final sweep for TODOs/FIXMEs/hardcoded secrets (none found), CONTRIBUTING.md and LICENSE reviewed, full backend/worker/frontend verification (101 + 13 + 9 tests, ruff/black/mypy/eslint/tsc all clean) and CI all green on the final push

## Security

Code execution happens in locked-down, ephemeral Docker containers (no network,
CPU/memory/PID limits, non-root, read-only base filesystem where practical,
automatic cleanup). This sandbox model is designed for **local/demo use** and
would need additional hardening (e.g. gVisor/Firecracker-level isolation, network
policy enforcement, syscall filtering) before handling hostile multi-tenant
workloads at scale. See [docs/security.md](docs/security.md) for the full model.

## License

MIT — see [LICENSE](LICENSE).
