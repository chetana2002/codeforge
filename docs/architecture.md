# Architecture

CodeForge is a **modular monolith + worker** system: one FastAPI process serves
the API, one separate worker process runs untrusted code, and they talk to
each other only through Postgres and Redis — never directly. This document
covers the shape of the system; see [`hld.md`](hld.md) for component
responsibilities, [`lld.md`](lld.md) for request-level detail, and
[`tradeoffs.md`](tradeoffs.md) for why each piece was chosen over the
alternatives.

## Why not microservices

The API's business logic (auth, projects, files, execution bookkeeping) is
one cohesive domain with one schema and no independent scaling need — splitting
it into services would add network calls, distributed transactions, and
deployment surface for no real benefit at this scale. The one component that
*does* have a genuinely different resource profile — untrusted code execution,
which needs Docker access and can hang or consume unbounded CPU/memory — is
already split out, as the worker. That is the actual scaling boundary in this
system, not an arbitrary domain split. See `tradeoffs.md` for the fuller
argument.

## System diagram

```
┌──────────────┐        HTTPS/cookies        ┌──────────────────┐
│   Browser    │ ───────────────────────────▶ │   Next.js (SSR)  │
│ (Monaco IDE) │ ◀─────────────────────────── │  frontend:3000   │
└──────────────┘         HTML/JSON            └────────┬─────────┘
                                                          │ REST + SSE
                                                          ▼
                                              ┌──────────────────────┐
                                              │   FastAPI (api:8000) │
                                              │  auth/projects/files │
                                              │  executions/metrics  │
                                              └──────┬────────┬──────┘
                                    ┌─────────────────┘        └──────────────────┐
                                    ▼                                              ▼
                          ┌──────────────────┐                          ┌──────────────────┐
                          │   PostgreSQL     │                          │      Redis       │
                          │  users/projects  │◀────────┐        ┌──────▶│ Streams (queue)  │
                          │  files/executions│         │        │       │ Pub/Sub (status) │
                          │  audit_logs      │         │        │       │ rate-limit keys  │
                          └──────────────────┘         │        │       └──────────────────┘
                                                        │        │
                                              ┌─────────┴────────┴──────┐
                                              │  Worker (worker:9100)    │
                                              │  Streams consumer        │
                                              │  writes Execution rows   │
                                              └────────────┬─────────────┘
                                                            │ Docker Engine API
                                                            ▼
                                              ┌──────────────────────────┐
                                              │  Ephemeral sandbox        │
                                              │  container (per run)      │
                                              │  no network, cpu/mem/pid  │
                                              │  limits, non-root, r/o fs │
                                              └──────────────────────────┘
```

## Request paths

**Synchronous (CRUD)** — auth, projects, files: browser → API → Postgres →
API → browser. Ordinary request/response, no queue involved.

**Asynchronous (execution)** — the one path that can't be synchronous, because
running arbitrary code takes an unbounded amount of time and must never block
an HTTP worker thread:

1. `POST /projects/{id}/execute` creates an `Execution` row (status `QUEUED`),
   commits it, then `XADD`s a job event to a Redis Stream. Returns `202` with
   the execution id immediately — it does not wait for the code to run.
2. The worker's consumer group reads the stream (`XREADGROUP`), looks up the
   execution, and transitions it to `RUNNING`.
3. The worker launches a locked-down Docker container, captures stdout/stderr/
   exit code, and writes the terminal status (`SUCCESS`/`FAILED`/`TIMEOUT`).
4. At each transition the worker also publishes to a Redis Pub/Sub channel.
   The API's `GET /executions/{id}/stream` endpoint (Server-Sent Events)
   subscribes to that channel and pushes the new state to any connected
   client — this is how the IDE shows "Running…" and then the result without
   polling.

The queue is the load-bearing decision here: without it, an execute request
would hold an API worker thread (and a Docker container) open for as long as
the code runs, and a slow/hung sandbox would degrade the whole API's
capacity to serve unrelated requests. See `execution-engine.md` for the full
state machine and `scalability.md` for how this queue behaves under load.

## Why the worker never talks to the API, and vice versa

The worker and API don't call each other's HTTP endpoints at all — they
communicate only by writing to Postgres and publishing to Redis. This is
deliberate: it means either process can be down without the other one
crashing (see `failure-scenarios.md`), and it means there's no service
discovery, no internal auth, and no API versioning problem between them —
just a shared schema and two well-documented Redis channels
(`codeforge:executions` the stream, `codeforge:execution-updates` the
pub/sub channel).

## Directory layout

```
codeforge/
├── frontend/    Next.js app (App Router), TanStack Query, Monaco
├── backend/     FastAPI app — api/application/domain/infrastructure/schemas/core
├── worker/      Execution worker — its own minimal ORM mirror, no shared package
├── infra/       Prometheus + Grafana provisioning
├── docs/        This directory
├── tests/e2e/   Playwright, runs against the real docker-compose stack
└── docker-compose.yml
```

`backend/app` is layered clean-architecture style: `api/routes` are thin
HTTP adapters, `application/services` hold business logic, `domain/models`
and `domain/enums` are the SQLAlchemy schema and state machines,
`infrastructure/` wraps Postgres/Redis clients, `schemas/` are the Pydantic
request/response contracts. `worker/` intentionally duplicates the handful of
ORM columns it actually touches (see the docstring in `worker/models.py`)
rather than sharing a package with the backend — the two are separate
deployables and a shared internal package would just be import-time coupling
with no real benefit, since the worker only ever needs a small slice of the
schema.
