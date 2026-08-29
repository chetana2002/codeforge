# Failure Scenarios

What happens when each dependency goes down, and why the system responds the
way it does. The guiding principle (see `hld.md`) is: **fail loud where
silent failure would corrupt correctness, fail soft where it would only cost
convenience.**

## Postgres is unreachable

**Effect**: every endpoint that touches the database fails. `GET /ready`
reports `database: "unavailable"` and increments `database_connection_errors`
(visible in `/metrics` and the Grafana dashboard). `GET /health` still
returns `ok` — it's a liveness check (is the process up and able to respond
at all), not a readiness check, so an orchestrator doesn't kill and restart a
perfectly healthy process just because a dependency is down.

**Worker behavior**: the worker's Streams consumer keeps running (Redis is
independent of Postgres), but every job it dequeues fails when it tries to
look up the `Execution` row, and — per the queue's at-least-once delivery
semantics (`execution-engine.md`) — is left un-ACKed and retried via
`XAUTOCLAIM` once Postgres comes back. No job is silently dropped; it just
queues up as pending retries.

**Recovery**: automatic once Postgres is reachable again — no manual
intervention, no data loss for anything that was already committed.

## Redis is unreachable

Redis serves three distinct roles here (queue, pub/sub, rate-limit counters),
and each one is designed to fail differently on purpose:

- **Job queue (execute requests)**: fails **loud**. `POST /projects/{id}/execute`
  raises `503 EXECUTION_QUEUE_UNAVAILABLE` if the publish fails, *after* the
  `Execution` row has already been committed as `QUEUED`. That row staying
  `QUEUED` with no job behind it is the deliberately-chosen failure mode —
  see the comment on `ExecutionService.create_and_enqueue`: publishing only
  after the commit is durable means a failed publish leaves a visible,
  retryable `QUEUED` row, rather than risking the reverse order (publish
  first) where a worker could dequeue a job for a row that doesn't durably
  exist yet.
- **Pub/sub (live SSE updates)**: fails **soft**. If Redis is down, the SSE
  endpoint's `pubsub.subscribe()` call itself fails, but the initial state is
  still sent (it comes from Postgres), and the frontend's `useExecutionStream`
  hook keeps its polling fallback (`useExecution`'s `refetchInterval`)
  regardless — a user sees the same result slightly later via polling
  instead of instantly via push. See `tradeoffs.md`, "SSE vs. WebSockets,"
  for why polling-as-fallback was the deliberate design rather than an
  afterthought.
- **Rate limiting**: fails **open**. `app/core/rate_limit.py` catches
  `RedisError` around the increment/check and lets the request through,
  logging a warning rather than blocking. An unprotected-against-abuse app is
  a better failure mode than a completely unusable one — rate limiting is a
  secondary defense here, not a correctness dependency.

**Worker behavior**: the consumer's `XREADGROUP` calls start failing; the
worker logs `xreadgroup_failed` and retries with a 1-second backoff rather
than crashing the process.

## The worker is down (API and Redis fine)

**Effect**: `POST /execute` still succeeds — the row is created and the job
is queued — but nothing consumes it. The execution sits at `QUEUED`
indefinitely. This is intentional and matches the spec this project follows:
*the API must never crash or degrade because the worker is unavailable* —
enqueueing and consuming are fully decoupled, so a worker outage is
invisible to every part of the system except "this specific execution hasn't
started yet," which is a normal, representable state (`QUEUED`), not an
error.

**Recovery**: automatic — the moment the worker comes back up, it drains the
stream from where it left off (consumer groups track position server-side in
Redis), including anything that piled up while it was down.

## A worker crashes mid-execution

Covered in detail in `execution-engine.md`'s "Known gap" section: a crash
after `RUNNING` but before a terminal state has no automatic recovery today,
because the state machine has no `RUNNING → QUEUED` transition. The
execution stays `RUNNING` forever from the system's point of view. The fix
(a periodic reaper sweeping for executions `RUNNING` past
`execution_timeout_seconds` and forcing them to `FAILED`) is a known,
scoped, not-yet-built piece of work — named here rather than hidden.

## The sandbox container itself misbehaves

Handled entirely within a single execution, with no effect on the rest of
the system:
- **Infinite loop / hang**: bounded by `container.wait(timeout=...)`; on
  timeout the container is force-killed and the execution recorded as
  `TIMEOUT`.
- **Fork bomb**: bounded by `pids_limit` at the container level — the
  container hits the cap and new processes fail to spawn, rather than
  exhausting the host.
- **Runaway memory**: bounded by `mem_limit`/`memswap_limit`; the container
  is OOM-killed by the kernel, which surfaces as a non-zero exit code and is
  recorded as `FAILED`.

None of these can affect a *different* execution, because every run gets its
own container, and the container is unconditionally removed in a `finally`
block regardless of how it ended.

## A whole host / all containers go down

Out of scope for this project's current phase — there's no multi-instance
API, no leader election, no distributed lock beyond what Redis Streams
consumer groups already provide. See `scalability.md` for what horizontal
scaling of the API and worker would actually require, and note that
Postgres and Redis themselves are still single instances in this setup —
production-grade HA for those is a managed-service concern (RDS Multi-AZ,
Redis with replicas), not something this application code implements itself.
