# Execution Engine

This covers the code-execution pipeline in detail: the state machine, the
queue's delivery semantics, and the sandbox itself. See `hld.md` for how this
fits into the overall system and `security.md` for the sandbox's threat
model specifically.

## State machine

```
QUEUED ──────┬──▶ RUNNING ──┬──▶ SUCCESS
             │              ├──▶ FAILED
             │              ├──▶ TIMEOUT
             │              └──▶ CANCELLED
             │
             └──────────────────▶ CANCELLED
```

`SUCCESS`/`FAILED`/`TIMEOUT`/`CANCELLED` are all terminal — no transition
leaves them. This is enforced in code
(`app/domain/enums/execution_status.py`), not just by convention: every
transition goes through `ExecutionService.transition()`, which checks
`ALLOWED_TRANSITIONS` and raises `InvalidExecutionTransitionError` on
anything not in that table. `test_execution_state_machine.py` asserts every
valid transition is allowed and every invalid one is rejected — including
transitions that look "reasonable" but aren't in the table, like
`RUNNING → QUEUED` (there's no way back to queued once a job has started;
see "Known gap" below for what that implies about recovery).

A cancel request only succeeds against `QUEUED` or `RUNNING` — cancelling an
already-terminal execution returns `409 EXECUTION_NOT_CANCELLABLE` rather
than silently no-op'ing, so a client always knows whether its cancel
actually did anything.

## Queue delivery semantics

The job queue is a Redis Stream (`codeforge:executions`), consumed via a
consumer group (`XREADGROUP`) — which gives **at-least-once** delivery: if
the worker crashes after reading a message but before acknowledging it
(`XACK`), that message stays in the group's Pending Entries List and a
periodic `XAUTOCLAIM` sweep (idle threshold: 60s) reclaims and redelivers it.

At-least-once means the same job can be delivered twice, so every handler is
written to be idempotent against redelivery: before doing any work, the
worker re-reads the execution's current status and no-ops unless it's still
`QUEUED`. A duplicate delivery of an already-`RUNNING` or terminal job is
just a wasted read, not a double-execution.

A message is only ACKed once the handler returns *without raising* — this
means a job that fails with a deliberate terminal status (`FAILED`,
`TIMEOUT`) is still ACKed (that's a successful *handling* of the job, even
though the code itself failed), while an unexpected exception in the
worker's own code leaves the message un-ACKed and eligible for retry.

**Known gap** (documented in `worker/consumer.py`'s module docstring): a job
that crashes *after* being marked `RUNNING` but before reaching a terminal
state has no automatic retry path, because the state machine has no
`RUNNING → QUEUED` transition — a redelivery of it is skipped as "not
queued" (the idempotency check above), and it's left stuck `RUNNING`
indefinitely. Recovering those requires a separate reaper (a periodic sweep
for executions `RUNNING` past their timeout, forcing them to `FAILED`) that
is out of scope for this project's current phase. This is a real,
acknowledged gap, not swept under the rug — see `failure-scenarios.md`.

### Race condition this queue actually hit, and how it was fixed

The API commits the `Execution` row to Postgres, *then* publishes the job
event — deliberately in that order (see the comment in
`ExecutionService.create_and_enqueue`), because the worker reads the row with
its own database connection, and an uncommitted (merely flushed) row is
invisible outside the API's own transaction. Even with that ordering, a fast
worker can dequeue and query for the row within single-digit milliseconds of
publish — faster than the commit's write becoming visible to a *new*
connection under Postgres's MVCC visibility rules in rare cases. The fix
(`ExecutionManager._exists_with_retry`) is a short bounded retry
(50ms/100ms/200ms backoff) before giving up and logging
`execution_not_found` — cheap insurance against a race that's real but rare.

## The sandbox

Each execution runs in its own container, created fresh and removed
unconditionally in a `finally` block regardless of outcome (`docker_runner.py`).

**Isolation:**
- `network_disabled=True` / `network_mode="none"` — no network access at all.
- `mem_limit` / `memswap_limit` — capped, and swap capped to the same value so
  memory pressure can't be dodged by swapping.
- `nano_cpus` — CPU share limit.
- `pids_limit` — caps process count, which is what actually stops a fork bomb
  (a memory or CPU limit alone doesn't).
- `user="1000:1000"` — never runs as root inside the container.
- `read_only=True` root filesystem, with a small `tmpfs` scratch directory for
  the one file being executed.
- `cap_drop=["ALL"]` + `security_opt=["no-new-privileges"]` — no Linux
  capabilities beyond the bare minimum, and no privilege escalation via
  setuid binaries.
- A wall-clock timeout (`container.wait(timeout=...)`); on timeout the
  container is force-killed and the run is recorded as `TIMEOUT`.

Every one of these is covered by a real integration test in
`worker/tests/test_sandbox.py` — not just configured, but *proven*: real
containers, asserting network access actually fails, a fork bomb actually
gets capped, the filesystem actually can't be written to outside the working
directory, and the container is actually gone afterward.

**Getting code into a read-only container** turned out to be the trickiest
part of this whole subsystem. The obvious approach — Docker's `put_archive()`
API, the normal way to inject a file into a container without a bind mount —
unconditionally rejects writes against *any* container with
`ReadonlyRootfs` set, confirmed empirically even against a path covered by
its own `tmpfs` mount, even after the container had started and that tmpfs
was genuinely mounted and writable from inside. Rather than drop `read_only`
to work around that, the source code is instead passed in as a
base64-encoded environment variable, and the container's own entrypoint
(`sh -c '...'`) decodes it into the tmpfs-mounted working directory via a
plain shell redirect before exec'ing the real run command — which is exempt
from the read-only check because it never goes through the Engine API's
write path at all.

This also sidesteps a Docker-outside-of-Docker bind-mount trap: the worker
itself runs inside its own container and talks to the *host's* Docker daemon
over the mounted socket, so any path the worker writes to on its own
filesystem doesn't exist from the host's point of view — a bind mount would
need a path that resolves on the host, which the worker's container
filesystem can't provide. An environment variable has no such
path-namespace mismatch, so it works regardless of where the worker itself
is running.

## Runtimes

`worker/runtimes/registry.py` maps a language string to a `RuntimeSpec`
(image, working directory, filename, run command, resource defaults).
Currently: Python 3.12 (`python:3.12-slim`) and Node 22
(`node:22-alpine`). Adding a language is one new `RuntimeSpec` plus a
registry entry — the sandbox runner itself is language-agnostic.
