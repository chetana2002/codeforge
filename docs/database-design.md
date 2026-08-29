# Database Design

PostgreSQL is the single source of truth for the whole system (see
`hld.md`). This document covers the schema, the reasoning behind the less
obvious choices, and the indexing strategy. See `tradeoffs.md` for *why
Postgres* over alternatives like MongoDB.

## Entity-relationship overview

```
users ──1:N── sessions
  │
  ├──1:N── projects ──1:N── files (self-referencing tree via parent_id)
  │                     │
  │                     └──1:N── executions ──1:N── execution_logs
  │
  ├──1:N── idempotency_keys ──N:1── executions
  │
  └──1:N── audit_logs   (no FK — see below)
```

All primary keys are UUIDv4, generated application-side (`default=uuid.uuid4`
in SQLAlchemy) rather than by the database — this keeps id generation
identical in tests, the app, and any future write path, and avoids a
round-trip to get an id back after insert.

## Tables

### `users`
`id`, `email` (unique, indexed), `hashed_password`, timestamps. Passwords are
hashed with bcrypt directly (not passlib — see `security.md` for why),
72-byte-truncated per bcrypt's own limit.

### `sessions`
One row per active refresh token. `refresh_token_hash` (unique, indexed) —
the raw token is never persisted, only its SHA-256 hash, so a database read
can't produce a usable session. `revoked_at` (nullable) marks logout/rotation
without deleting the row, preserving an audit trail of session history.

### `projects`
`owner_id` FK → `users.id`, `language`, `visibility`. Index:
`(owner_id, created_at)` — the dashboard and project list both query "this
user's projects, newest first," and a composite index serves that directly
without a sort step.

### `files`
Adjacency list (`parent_id` FK → `files.id`, nullable for root-level items) —
not a materialized path. See `tradeoffs.md` for the comparison, but the short
version: this project needs cheap renames/moves (a single-row `UPDATE`) far
more than it needs cheap "give me the whole path as a string," and an
adjacency list is a single-row update either way while a materialized path
would need to rewrite every descendant's path on a folder move.

Sibling-name uniqueness ("no two files named `main.py` in the same folder")
is enforced by the database, not just application code, via two **partial
unique indexes** rather than one:

```sql
CREATE UNIQUE INDEX ix_files_unique_root_name
  ON files (project_id, name) WHERE parent_id IS NULL;
CREATE UNIQUE INDEX ix_files_unique_child_name
  ON files (project_id, parent_id, name) WHERE parent_id IS NOT NULL;
```

Two indexes, not one, because Postgres treats every `NULL` as distinct for
uniqueness purposes — a single index on `(project_id, parent_id, name)` would
never actually reject two root-level files with the same name, since
`parent_id IS NULL` never equals itself. Splitting the root case into its own
`WHERE parent_id IS NULL` index closes that gap.

### `executions`
`project_id`/`file_id`/`user_id` FKs (all `CASCADE`), `status` (see
`execution-engine.md` for the state machine), `stdout`/`stderr` (`TEXT`,
unbounded — sandboxed processes are capped by wall-clock timeout, not output
size, so no length cap is needed here), `exit_code`, `duration_ms`,
`idempotency_key`. Index: `(project_id, created_at)` for the
per-project history view, plus a plain index on `status` for the worker's own
lookups and any future "show me all QUEUED executions" admin/ops query.

### `execution_logs`
Append-only audit trail of state transitions (`from_status`, `to_status`,
optional `message`) — deliberately separate from `executions.stdout/stderr`,
which hold captured process output, not a log of status changes. Every
`ExecutionService.transition()` call writes one of these, so a stuck or
misbehaving execution has a full history of what happened and when.

### `idempotency_keys`
`UNIQUE(user_id, key)` — a client-supplied `Idempotency-Key` header maps to
exactly one execution per user. A retried request with the same key and the
same underlying (project, file) returns the original execution instead of
creating a duplicate job; the same key reused for a *different* request is
rejected with `409` rather than silently executed. See `api.md` for the
request-hash comparison this relies on.

### `audit_logs`
`user_id`, `event_type` (9 values — login/logout, project/file
created/deleted, execution started/completed/cancelled), `resource_type` +
`resource_id`, `ip_address`, `details` (JSON). `resource_id` is **not** a
foreign key, on purpose: the row it names can legitimately be gone by the
time anyone reads the audit log — a `PROJECT_DELETED` event's whole point is
to outlive the project it describes. An FK here would either block the
delete or force `ON DELETE SET NULL`/cascade, either of which defeats the
audit trail's purpose. Index: `(user_id, created_at)` for "this user's
activity, newest first," which is the only query pattern the audit log
actually serves right now (`GET /audit-logs`).

## Cascade strategy

Every FK in this schema is `ON DELETE CASCADE`, deliberately uniform: delete
a user and their projects, files, executions, sessions, and audit logs go
with them; delete a project and its files/executions go with it. The
alternative (soft deletes, or restricting deletes until children are gone)
adds real complexity — every query needs a `deleted_at IS NULL` filter, and
every delete becomes multi-step — for a benefit (recoverable deletes) this
project doesn't need. If that need appears later, it's an additive
migration (a `deleted_at` column), not a rearchitecture.

## Migrations

Alembic, autogenerated then hand-reviewed per phase (see the commit history
in `alembic/versions/`) — never hand-written from scratch, to keep the
migration and the SQLAlchemy model from drifting apart. `alembic upgrade
head` is idempotent and safe to run against an already-current database (it's
run as its own CI/deploy step, not baked into application startup — see
`deployment.md` for why).
