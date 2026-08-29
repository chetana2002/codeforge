# Security

This covers the security model across authentication, data access, the
execution sandbox, and the network/HTTP surface. Sandbox isolation detail
lives in `execution-engine.md`; this document covers *why* those specific
controls, plus everything outside the sandbox.

## Authentication

**Password storage**: bcrypt, applied directly (not via passlib — an earlier
version of this project used passlib and hit a real incompatibility with
bcrypt ≥4.1's internal API changes; bcrypt's own `hashpw`/`checkpw` are used
directly instead). Passwords are truncated to 72 bytes before hashing —
bcrypt's algorithm silently ignores anything past that length, so truncating
explicitly on both hash and verify keeps the two paths in agreement rather
than one of them being surprised by the algorithm's own limit.

**Session tokens**: two tokens, not one, on purpose:
- A **JWT access token** (15 min expiry, `HttpOnly` cookie) — stateless,
  verified by signature alone, no database lookup on every request. Short
  expiry bounds how long a stolen token is useful.
- An **opaque refresh token** (7 day expiry, `HttpOnly` cookie) — a
  high-entropy random string (`secrets.token_urlsafe(48)`), of which only the
  SHA-256 hash is ever persisted (in `sessions.refresh_token_hash`). A
  database read alone can never produce a usable token.

`POST /auth/refresh` **rotates** the refresh token on every use: it issues a
new one and revokes the old, rather than reusing the same refresh token for
the full 7 days. This means a stolen refresh token is only useful until its
next legitimate use — after that, both the attacker's and the real user's
copies stop working, which is itself a detectable signal (the real user gets
logged out unexpectedly) rather than a silent, indefinite compromise.

Both cookies are `HttpOnly` (unreachable from JavaScript, closing off the
main XSS-driven token-theft path) and `SameSite=Lax`. `Secure` is
environment-gated (`COOKIE_SECURE`) — on in any real deployment, off only for
local HTTP development.

## Authorization

Every resource lookup is scoped to the requesting user at the query level,
not filtered after the fact — `ProjectService.get_owned(user_id, project_id)`
joins on ownership as part of the `WHERE` clause, so a project belonging to
another user doesn't just get filtered out of a result set, it never matches
the query at all and returns a `404` indistinguishable from "doesn't exist."
This is deliberate: returning `403 Forbidden` for someone else's resource
confirms that resource *exists*, which is itself information leakage for an
ID-guessing attacker.

## Path traversal prevention

File and folder names are validated to be a **single path segment** —
`^[^/\\\x00]+$`, and neither `.` nor `..` — at the Pydantic schema layer
(`app/schemas/file.py`), before a name is ever combined with a parent to
form a path. This isn't "traversal sequences are stripped or rejected
downstream" — it's structural: since the tree is an adjacency list keyed by
`parent_id` (not a filesystem path string, see `database-design.md`), there
is no path string for a traversal sequence to act on in the first place. The
validation exists to keep names sane and single-segment, which as a side
effect makes traversal impossible rather than merely blocked.

## HTTP surface

- **CORS**: explicit origin allowlist (`CORS_ORIGINS`), credentialed
  (`allow_credentials=True`, required for cookie-based auth to work
  cross-origin at all) — no wildcard origin, which the credentials flag
  would make a browser reject anyway.
- **Security headers** (`SecurityHeadersMiddleware`, applied to every
  response): `X-Content-Type-Options: nosniff` (this API only ever serves
  JSON; stop a browser from executing a response as anything else),
  `X-Frame-Options: DENY` (nothing here is meant to be framed),
  `Referrer-Policy: strict-origin-when-cross-origin`, a restrictive
  `Permissions-Policy`, and `Strict-Transport-Security` gated on
  `ENVIRONMENT=production` (asserting HSTS over plain local HTTP would be a
  no-op the browser ignores anyway, so it's only sent where it's meaningful).
- **Rate limiting**: Redis-backed, per `RATE_LIMITED` responses on login
  (5/min/IP), execution (20/min/user), and project creation (20/min/user).
  Fails *open* on a Redis outage — see `failure-scenarios.md` for why that's
  the right default here specifically.
- **Validation errors never leak internals**: Pydantic validation failures
  are caught by a global exception handler and re-encoded into the
  `{data, error}` envelope (`VALIDATION_ERROR`) rather than FastAPI's default
  representation, which can otherwise include raw exception objects that
  aren't JSON-serializable and would 500 instead of 422.
- **Unhandled exceptions** are caught by a top-level handler that logs the
  real error server-side but returns a generic `INTERNAL_ERROR` message to
  the client — a stack trace or raw exception message is never sent over the
  wire.

## Secrets

`SECRET_KEY` (JWT signing), database credentials, and everything else
sensitive are environment variables only, sourced from `.env` (gitignored;
`.env.example` documents every variable with a placeholder, never a real
value). No secret is hardcoded anywhere in the codebase — this was verified
by inspection at each phase of this build, not just asserted. Structured
logs (`app/core/logging.py`) redact known-sensitive key names before they're
ever written, so a password or token accidentally passed into a log call
doesn't end up in log output verbatim.

## Audit logging

Nine event types (login/logout, project/file created/deleted, execution
started/completed/cancelled) are recorded to an append-only `audit_logs`
table — see `database-design.md` for the schema and `hld.md` for where each
event is emitted. Each write happens in the same database transaction as the
action it documents, so an audit record can't exist for an action that then
rolled back, or vice versa. Available to the user who generated it via
`GET /audit-logs`.

## The sandbox, briefly

Untrusted code never runs inside the API process — it always goes through
the worker's Docker sandbox: no network, CPU/memory/PID limits, non-root,
read-only root filesystem, all Linux capabilities dropped, ephemeral
(destroyed after every run regardless of outcome). Full detail, including
the two things that turned out to matter most in practice (PID limits being
what actually stops a fork bomb, and the read-only-rootfs code-injection
problem), is in `execution-engine.md`.

## Known limitations

This is a portfolio/demo-scale security model, not a hardened multi-tenant
platform, and the gaps are worth naming rather than glossing over:

- **Container-level isolation, not VM-level.** Docker's namespace/cgroup
  isolation is real but shares a kernel with the host; a kernel
  vulnerability could theoretically escape it. Hardening this further means
  gVisor or Firecracker-level isolation — deliberately out of scope here
  (see `tradeoffs.md`, "Docker vs. Firecracker") because it's a
  meaningfully bigger operational lift than this project's scope justifies,
  not because the tradeoff is unknown.
- **No 2FA, no email verification, no password-reset flow.** Registration
  and login are real and correct, but the full account-lifecycle surface a
  production consumer product would need isn't built.
- **Rate limiting is fixed-window**, which allows short bursts across a
  window boundary — acceptable for blunting abuse, not for a strict
  billing-grade quota (see `tradeoffs.md`).
