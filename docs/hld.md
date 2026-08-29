# High-Level Design

See [`architecture.md`](architecture.md) for the system diagram and request
paths this document assumes.

## Components and responsibilities

| Component | Responsibility | Does NOT do |
|---|---|---|
| **Frontend** (Next.js) | Auth UI, project/file management UI, Monaco editor, live execution view (SSE), execution history | Never executes user code; never talks to Postgres/Redis directly |
| **API** (FastAPI) | Auth, CRUD for projects/files, enqueueing executions, rate limiting, metrics, SSE fan-out | Never runs user code itself — only ever enqueues a job |
| **Worker** | Consumes execution jobs, launches sandboxed containers, writes results back to Postgres, publishes status | Never serves HTTP; has no user-facing surface at all |
| **Postgres** | System of record for everything (users, projects, files, executions, audit log) | No caching/queue role |
| **Redis** | Job queue (Streams), live-status fan-out (Pub/Sub), rate-limit counters | Not the source of truth for anything — every value it holds is either transient (queue/pubsub) or reconstructible from Postgres |

## Core flows

### Authentication

Cookie-based, two tokens: a short-lived (15 min) JWT access token and a
longer-lived (7 day) opaque refresh token, both `HttpOnly`. The refresh token
is never stored raw — only its SHA-256 hash, in a `sessions` row — so a
database leak doesn't hand out usable tokens. `/auth/refresh` rotates the
refresh token on every use (issues a new one, revokes the old), which bounds
the damage of a stolen refresh token to a single use before it's invalidated.
See `security.md` for the full threat model.

### Project / file management

Files are a self-referencing adjacency-list tree (`parent_id` FK on the
`files` table) scoped to a project. Path-traversal is prevented at the model
level, not just the API layer: file *names* are validated to be a single
path segment (no `/`, no `..`) before they're ever combined with a parent to
form a path, so there's no path string to traverse in the first place — see
`security.md`.

### Code execution (the core flow)

This is the one flow that spans all three services and is worth walking
through as a single narrative — see `execution-engine.md` for the byte-level
detail of the sandbox itself:

1. **Enqueue** (API): `POST /projects/{id}/execute` validates ownership,
   creates an `Execution` row as `QUEUED`, commits it, then publishes a job
   event to a Redis Stream. Returns `202 Accepted` immediately.
2. **Dequeue** (Worker): the worker's consumer group reads the stream. Before
   doing anything it re-reads the execution's status from Postgres and
   no-ops if it isn't `QUEUED` — this makes redelivery (Streams gives
   *at-least-once* delivery) safe without extra bookkeeping.
3. **Run** (Worker → Docker): the worker builds a locked-down container spec
   (no network, CPU/memory/PID limits, non-root, read-only rootfs) for the
   requested language, starts it, waits up to `EXECUTION_TIMEOUT_SECONDS`,
   captures stdout/stderr/exit code, and removes the container unconditionally.
4. **Report** (Worker → Postgres + Redis): writes the terminal status,
   stdout/stderr, exit code, and duration to the `Execution` row, then
   publishes the new status on a Pub/Sub channel.
5. **Push** (API → Browser): a connected SSE client
   (`GET /executions/{id}/stream`) receives the pub/sub message, re-reads the
   execution from Postgres (the pub/sub payload is just a "something changed,
   go look" signal — Postgres is still the source of truth), and streams the
   new state down to the browser.

### Observability

Every service exposes `/metrics` in Prometheus text format — the API on its
normal port, the worker on a dedicated metrics-only port (it has no other
HTTP surface). Both `/health` (liveness) and `/ready` (checks Postgres and
Redis connectivity) exist on the API for orchestrator health checks. See
`observability.md` for the full metric list and what each one is for.

## Design principles this system follows

- **The queue is the trust boundary between "fast" and "slow."** Anything
  that can take an unbounded amount of time (running arbitrary code) goes
  through the queue; everything else is synchronous CRUD. This is the single
  biggest structural decision in the system — see `tradeoffs.md`
  ("sync vs. async").
- **Postgres is the only source of truth.** Redis holds nothing that can't be
  regenerated or that isn't inherently transient (a queue entry, a pub/sub
  notification, a rate-limit counter). If Redis is flushed, the system loses
  in-flight jobs and live-push capability, not data.
- **Fail loud where correctness matters, fail soft where availability
  matters.** Enqueueing an execution raises a `503` if Redis is down (an
  execution that's recorded as `QUEUED` but never actually queued is a silent
  bug); rate limiting fails *open* if Redis is down (an unprotected app is
  better than a completely unusable one). See `failure-scenarios.md`.
- **Every external boundary validates.** File names, execution ownership,
  request bodies (Pydantic) — nothing crosses a trust boundary unchecked.
