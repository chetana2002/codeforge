# Low-Level Design

This picks up where `hld.md` leaves off — request-level and algorithm-level
detail for the parts of the system with the most non-obvious internals. See
`database-design.md` and `execution-engine.md` for the schema and sandbox
detail this document assumes.

## Request lifecycle through the API

Every request passes through, in order: `SecurityHeadersMiddleware` →
`MetricsMiddleware` → `CORSMiddleware` → FastAPI routing → dependency
resolution → the route handler. The two custom middlewares are plain ASGI
(not Starlette's `BaseHTTPMiddleware`) specifically to avoid interfering with
the SSE endpoint's streaming — see `observability.md` for why. Dependencies
(`get_db`, `get_current_user`, the rate limiters) are resolved once per
request and cached across every place they're used in that request — a route
that depends on both `get_current_user` directly *and* a rate-limit
dependency that itself depends on `get_current_user` does not run that
auth check twice or issue two database queries.

## The SSE endpoint's exact mechanics

`GET /executions/{id}/stream` (`app/api/routes/executions.py`) does ownership
verification once, outside the generator, so an unauthorized or unknown id
returns a normal `404` JSON error rather than a `200` stream that immediately
errors. Inside the generator:

1. **Subscribe before the first state read** — not after. A status change
   that lands in the gap between "check current state" and "start listening"
   would otherwise be missed entirely; subscribing first means the worst
   case is one redundant duplicate event, never a lost one.
2. **Yield the current state immediately.** If it's already terminal, the
   generator returns right there — no reason to hold a subscription open for
   an execution that's already done.
3. **Poll the pub/sub subscription with a keepalive timeout**
   (`execution_stream_keepalive_seconds`, default 5s in production, 1s in
   tests). No message within that window sends an SSE comment (`: keepalive`)
   to keep the connection alive through intermediate proxies/load balancers
   that might otherwise time out an idle connection.
4. **A max-duration cutoff** (`execution_stream_max_seconds`) ends the stream
   even if the execution never reaches a terminal state and the client never
   disconnects — because `request.is_disconnected()` is *not* reliable
   enough to depend on alone. This was confirmed directly, not assumed:
   under httpx's ASGI test transport, `is_disconnected()` never returns
   `True` for a client that simply stops reading, which — before the cutoff
   was added — left test generators running for their full duration and
   holding a database transaction open long enough to block a later test's
   schema teardown.
5. **The database session is closed explicitly in the generator's `finally`**,
   rather than left to whenever the ASGI response finishes flushing and
   FastAPI's own dependency cleanup runs. Those can be meaningfully far
   apart in time for a long-lived streaming response; closing explicitly
   frees the connection back to the pool the moment the generator is
   actually done with it.

### A real bug this endpoint hit, for what it's worth

The `db` session backing this generator is long-lived — it's used for both
the initial read and every re-read triggered by a pub/sub message, across
the whole life of the stream. SQLAlchemy's identity map means a second query
for a row that's *already loaded* in that session does not, by default,
refresh that row's attributes from a fresh `SELECT` — it hands back the
already-loaded Python object as-is. In practice this meant a status change
made by a *different* session (the worker, committing a transition) was
invisible to this endpoint's re-read: it kept returning the stale
in-memory object. The fix is `db.expire_all()` immediately before the
re-fetch, forcing a real query. This is a specific, non-obvious SQLAlchemy
footgun for exactly this pattern — a session that outlives a single request
and re-reads the same rows — worth naming for the next person who hits it.

## File tree: move and rename

Moving a file/folder is a single-row `UPDATE` of `parent_id` (and/or `name`)
— the adjacency-list design pays for itself here (`database-design.md`).
Before that update, `FileService._would_create_cycle` walks *up* from the
proposed new parent toward the root, checking whether it ever reaches the
file being moved:

```python
current = new_parent_id
while current is not None:
    if current == file_id:
        return True  # would create a cycle
    current = <current's own parent_id, looked up>
return False
```

This catches both "move a folder into itself" and "move a folder into one of
its own subfolders" with the same check — the latter is really just the
former, one or more levels removed, and a single upward walk covers all
depths without needing to know how deep the tree is ahead of time. Rejected
with `400 INVALID_MOVE` before the update is attempted.

Sibling-name collisions (moving/renaming into a spot where a same-named item
already exists) are *not* pre-checked in application code — the update is
attempted, and Postgres's own partial unique index
(`database-design.md`) is the actual enforcement. On the resulting
`IntegrityError`, the transaction is rolled back and it's re-raised as
`409 FILE_ALREADY_EXISTS`. Letting the database be the single source of
truth for this constraint (rather than a `SELECT`-then-`INSERT` check in
application code) avoids a TOCTOU race between two concurrent renames
targeting the same name.

## Frontend: live state without a global store

There's no Redux/Zustand-style global client state in this app — TanStack
Query's cache *is* the state layer. The interesting piece is how the SSE
push and the polling fallback both feed the same cache entry without
conflicting:

- `useExecution(id)` is a normal query, keyed on `["executions", id]`, with a
  `refetchInterval` that polls every second *only* while the execution is
  non-terminal (checked against `TERMINAL_STATUSES` on each tick, so polling
  stops itself the instant a terminal status is observed, without needing an
  external signal to turn it off).
- `useExecutionStream(id)` opens an `EventSource` against the same endpoint
  and, on every message, calls `queryClient.setQueryData(["executions", id],
  execution)` — the *same* cache key `useExecution` reads. It never issues
  its own network request through TanStack Query; it just writes into the
  cache that other hook already owns.

Any component rendering via `useExecution` re-renders immediately when
either the poll *or* the SSE push updates that cache entry — they're not two
competing sources of truth, they're two producers writing into one. If SSE
is unavailable (a proxy that buffers or kills long-lived connections), the
poll still updates the same cache on its own 1-second cadence — degraded
latency, not a broken feature. This is exactly the fallback described in
`tradeoffs.md`'s SSE-vs-WebSockets section, made concrete.
