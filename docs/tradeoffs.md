# Tradeoffs

The reasoning behind every major architectural choice in this project,
including what was explicitly ruled out and why. Each section states the
alternative fairly — these are real tradeoffs, not strawmen.

## Modular monolith + worker, not microservices

**Chosen**: one FastAPI process for all CRUD (auth/projects/files/executions
bookkeeping), one separate worker process for code execution, communicating
only through Postgres and Redis.

**Alternative**: split auth, projects, files, and executions into
independently-deployed services.

**Why not microservices**: the API's domains share one schema, one
transaction boundary, and have no independent scaling profile from each
other — splitting them would add network calls, distributed-transaction
complexity, and deployment surface for domains that already scale together
fine as one process. The piece of this system that *does* have a genuinely
different resource profile — execution, which needs Docker access and can
hang or spike CPU/memory — is already split out, as the worker. That's the
real seam in this system; slicing along business-domain lines instead
(auth-service, project-service, ...) would be organizational cargo-culting,
not a response to an actual scaling or team-boundary need. See `hld.md`.

## Redis Streams, not Kafka

**Chosen**: Redis Streams for the execution job queue.

**Alternative**: Kafka (or another dedicated log-based broker).

**Why Streams**: this project needs consumer groups, at-least-once delivery,
and a retry/reclaim mechanism for crashed consumers — Streams provides all
three (`XREADGROUP`, `XACK`, `XAUTOCLAIM`) natively. Redis is *already* a
hard dependency here for pub/sub (SSE fan-out) and rate-limit counters, so
Streams adds a queue with zero new infrastructure, versus Kafka's own
cluster, ZooKeeper/KRaft, and operational surface. Kafka wins decisively at
much higher sustained throughput and when you need long-term log retention
and replay for many independent consumer groups reading the same topic
history — neither of which this project needs: job events are consumed
once and are irrelevant afterward. If execution volume ever reached a scale
where Kafka's partition-level parallelism and cross-datacenter replication
actually mattered, that would be the point to revisit this — not before.

## SSE, not WebSockets

**Chosen**: Server-Sent Events for live execution status
(`GET /executions/{id}/stream`).

**Alternative**: WebSockets.

**Why SSE**: the data flow here is one-directional (server → client status
updates) — the client never needs to send anything over the same channel
once the stream is open. SSE is plain HTTP (works through the same
infrastructure as every other endpoint, no separate protocol upgrade to
reason about), has automatic browser-native reconnection built into
`EventSource`, and is simpler to implement correctly on both ends. WebSockets
would be the right call if this needed bidirectional live communication —
collaborative editing, a chat feature — which this project doesn't. The
concrete cost paid for SSE: `request.is_disconnected()` is unreliable enough
under some ASGI transports (confirmed directly during this project's own SSE
testing — see the docstring on `stream_execution`) that the endpoint also
needs a max-duration cutoff as a second line of defense, not just disconnect
detection alone. That's a real, specific cost of SSE's simpler model, paid
knowingly.

## Postgres, not MongoDB

**Chosen**: PostgreSQL, fully relational schema with foreign keys.

**Alternative**: MongoDB or another document store.

**Why Postgres**: this data is inherently relational — a user owns projects,
a project owns files and executions, an execution belongs to a file and a
project and a user — and the relationships need to be *enforced*, not just
modeled: cascading deletes, foreign-key integrity, and the file tree's
sibling-name uniqueness (`database-design.md`) are all database-level
guarantees here, not application-code discipline that could silently drift.
Postgres's `JSON` column type (used for `audit_logs.details`) covers the one
place this project actually wants schema flexibility, without giving up
relational integrity everywhere else. MongoDB would be the better fit for
data that's naturally document-shaped with few cross-document relationships
— this project's data is the opposite of that.

## Async job processing, not synchronous execution

**Chosen**: `POST /execute` returns `202 Accepted` immediately; the actual
run happens on a worker, asynchronously, with the client polling or
subscribing to SSE for the result.

**Alternative**: run the code synchronously inside the request handler and
return the result directly.

**Why async**: this is the single most load-bearing decision in the system
(see `hld.md`). Running arbitrary, potentially-slow or hanging code
synchronously inside an API request would tie up an API worker thread (and a
Docker container) for as long as that code runs — a single slow or
adversarial execution would directly degrade every *other* user's ability to
get an API response, since threads/connections are a shared, finite
resource. Decoupling via a queue means the API's own responsiveness is
completely insulated from how long or badly user code behaves. The cost:
genuine complexity — a state machine, delivery semantics, idempotency,
and a live-update mechanism (SSE) so the client isn't just polling blindly
— all covered in `execution-engine.md`. That complexity is the price of the
insulation, and it's worth it specifically because the thing being run is
untrusted.

## Docker sandboxing, not Firecracker/gVisor

**Chosen**: standard Docker containers with a hardened configuration (no
network, resource limits, non-root, read-only rootfs, dropped capabilities —
`execution-engine.md`).

**Alternative**: Firecracker microVMs (what AWS Lambda and Fly.io machines
use) or gVisor (a user-space kernel that intercepts syscalls).

**Why Docker**: it's the isolation primitive every engineer already knows,
needs no specialized host kernel support or a custom VMM, and — with the
specific hardening applied here — is genuinely sufficient to safely run
untrusted code for a portfolio/demo-scale application, which is what this
project's own tests actually prove (`test_sandbox.py`: network access
blocked, fork bombs capped, filesystem read-only outside the working
directory, containers always cleaned up). The real, acknowledged gap: Docker
containers share the host kernel, so a kernel-level vulnerability is a
theoretical escape path that VM-level isolation (Firecracker) or a
syscall-filtering user-space kernel (gVisor) would close. That's the right
next step *if* this ever needed to safely run hostile, adversarial code from
untrusted strangers at real scale — a meaningfully bigger operational lift
(a custom VMM, different orchestration, different cold-start
characteristics) than this project's current scope justifies. Named directly
in `security.md`'s "Known limitations," not hidden.

## REST, not GraphQL

**Chosen**: REST, with a consistent `{data, error}` envelope on every
response.

**Alternative**: GraphQL.

**Why REST**: the API's resources map cleanly onto REST verbs and don't have
the deeply nested, client-driven-shape query pattern GraphQL is built to
solve — a project's files, a file's content, an execution's status are each
naturally one resource, one endpoint. REST also composes better with plain
HTTP tooling this project already leans on: standard HTTP caching semantics,
`curl`/browser-native testing, OpenAPI-generated docs (FastAPI's built-in
`/docs`) for free, and Server-Sent Events (which needs a plain HTTP GET, not
a GraphQL query) for the live-execution flow. GraphQL earns its complexity
when clients have genuinely varied data-shape needs from the same
underlying resources (a mobile client wanting a thin slice of a `Project`,
a dashboard wanting a deeply nested one) — this project has one frontend
with predictable, well-known query shapes, so that flexibility isn't
buying anything here.
