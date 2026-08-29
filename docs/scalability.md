# Scalability

How this architecture would scale toward the kind of numbers the original
spec named — 1M users, 100K executions/minute — and, just as importantly,
which parts of the *current* implementation would need to change first. This
is deliberately honest about what's built vs. what the architecture merely
*allows for*: nothing here has actually been load-tested at that scale.

## What scales without any code change

- **The API is stateless.** Auth is a signed JWT plus a database-backed
  refresh token, not an in-memory session — any number of API instances can
  serve any request behind a plain load balancer. No sticky sessions needed.
- **The worker is horizontally scalable by construction.** Redis Streams
  consumer groups exist specifically so multiple consumers can read from the
  same stream and each message goes to exactly one of them — running N
  worker replicas today, unmodified, means N-way parallel execution
  throughput. The single-worker setup in `docker-compose.yml` is a dev/demo
  choice, not an architectural ceiling.
- **Redis Streams is a real distributed queue**, not a toy — it has
  consumer-group semantics, pending-entry tracking, and claim/reclaim
  built in, which is the whole reason worker scaling above is "just run more
  replicas" rather than requiring new coordination code.

## What becomes the actual bottleneck, roughly in order

1. **The sandbox itself.** Running untrusted code in a Docker container has
   real per-execution overhead (container create/start/teardown — on the
   order of hundreds of milliseconds to a few seconds observed during this
   project's own testing). At 100K executions/minute (~1,700/second), this is
   the dominant cost by far, and it's a *worker replica count × host CPU/
   Docker daemon throughput* problem, not a code problem — this is where a
   move to Firecracker-style microVMs (see `tradeoffs.md`) would actually
   pay for itself: faster cold-start than a full container, and higher
   density per host.
2. **Postgres**, specifically write throughput on `executions`. Every
   execution is at least 2 writes (create as `QUEUED`, then a terminal
   update) plus an `execution_logs` row per transition. At high volume this
   is a straightforward, well-understood scaling problem — read replicas for
   the history/list endpoints (which don't need read-your-writes
   consistency the way the execute-then-poll flow does), and eventually
   partitioning `executions`/`execution_logs` by time, since old executions
   are read rarely and mostly for history browsing.
3. **A single Redis instance** becomes both a throughput and an availability
   single point of failure at real scale. Redis Cluster (for the Streams
   queue) or a managed Redis with replicas (for pub/sub and rate limiting)
   is the standard next step — nothing about the code assumes a single Redis
   node, since all access goes through the one `get_redis()`/
   `create_redis_client()` factory per service.
4. **SSE fan-out.** Server-Sent Events hold one long-lived connection per
   watching client on whichever API instance served it. That's fine at this
   project's scale; at real scale, "which API instance is this user's SSE
   connection on" becomes a real routing question (session affinity, or a
   dedicated fan-out layer). This is one of the concrete costs weighed
   against WebSockets in `tradeoffs.md` — SSE was still the right choice
   *for this project's scope*, but it's not free at 1M-user scale.

## What's already designed to survive scale, not just single-node dev

- **Idempotency keys** mean a client retrying a timed-out `execute` request
  (which is *more* likely, not less, under load) doesn't create duplicate
  jobs.
- **At-least-once queue delivery + idempotent job handling** means worker
  crashes and restarts under load (autoscaling churn, spot-instance
  termination) don't lose or double-run jobs.
- **Rate limiting** exists specifically to survive one misbehaving client at
  the expense of everyone else's fair share, which matters more, not less,
  as user count grows.

## What would need to be *built*, not just scaled

- The `RUNNING`-crash reaper named in `failure-scenarios.md` — at low volume
  a stuck execution is a rare annoyance; at high volume with frequent worker
  churn (autoscaling, spot termination) it's a real, regularly-occurring
  problem that needs automatic recovery, not manual intervention.
- Horizontal Postgres write scaling (sharding by user or project) once a
  single primary's write throughput is the ceiling — not needed at any scale
  this project has actually run at, but the schema's UUID primary keys
  (rather than serial/auto-increment) were chosen partly so that door stays
  open without an id-collision migration later.
- A queue-depth-based autoscaling policy for the worker fleet — `queue_depth`
  is already exported as a Prometheus gauge (`observability.md`)
  specifically so this is a metrics query away, not a new instrumentation
  project, once there's an autoscaler to wire it into.
