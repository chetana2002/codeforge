# Deployment

## Local development

```bash
cp .env.example .env   # adjust if needed — defaults work out of the box
docker compose up -d --build
docker compose exec api alembic upgrade head
```

This brings up Postgres, Redis, the API, the worker, the frontend, and
Prometheus/Grafana. Every host port is remapped off its default
(`API_PORT_HOST=8001`, `FRONTEND_PORT_HOST=3002`, `POSTGRES_PORT_HOST=5435`,
`REDIS_PORT_HOST=6381`, `GRAFANA_PORT_HOST=3003`,
`PROMETHEUS_PORT_HOST=9091`) so this stack doesn't collide with other
projects that might already be using the standard ports on the same host —
see `.env.example` for the full, commented list. Migrations are run as an
explicit separate step, never automatically on API startup — see
"Why migrations aren't automatic" below.

Sandbox runtime images (`python:3.12-slim`, `node:22-alpine`) are pulled by
the worker on first use if not already present locally; pre-pulling them
(`docker pull python:3.12-slim node:22-alpine`) avoids a slow first
execution.

## Why migrations aren't automatic

Running `alembic upgrade head` inside the API's own startup path is a common
shortcut, and a real production hazard once there's more than one API
replica: two instances starting simultaneously (a rolling deploy, an
autoscale event) would both try to apply the same migration concurrently.
Running it as its own explicit step — a CI/CD pipeline stage, or a one-shot
job before the new API version starts serving traffic — means it happens
exactly once per deploy, deterministically, and a migration failure is a
distinct, visible pipeline failure rather than a race condition inside a
running API process.

## Does this run on Vercel?

**No, not as a whole** — the architecture doesn't fit a serverless model:

- **Frontend (Next.js)** would deploy to Vercel fine on its own.
- **The worker is the actual blocker.** It needs a real Docker daemon to
  launch locked-down sandbox containers per execution (`execution-engine.md`).
  Serverless functions have no Docker access at all, under any
  configuration — this isn't a config problem, it's a fundamental capability
  mismatch.
- **The API** could technically run as serverless functions, but it's built
  as a long-running ASGI process — the SSE endpoint holds an open connection
  per client, and the Redis Streams consumer group model (on the worker
  side, but conceptually the same class of thing) assumes a persistent
  process, not a request-scoped function invocation.
- **Postgres/Redis** need managed hosting regardless of where the app layer
  runs — not Vercel's concern either way.

**Realistic shape**: frontend on Vercel (optional — it runs fine anywhere
that serves a Next.js app), API + worker on a host that provides a real
Docker socket and long-running processes — Fly.io, Railway, Render, or a
plain VPS/EC2 instance running `docker-compose.yml` directly, which is
already deploy-ready for that kind of host as-is. Postgres/Redis via a
managed provider (RDS/Neon/Supabase for Postgres; ElastiCache/Upstash for
Redis) rather than the containers this repo's compose file runs for local
dev — those are conveniences for a laptop, not a production topology.

## Environment configuration

Every setting is an environment variable, documented with a placeholder (not
a real value) in `.env.example` — `SECRET_KEY`, database/Redis URLs, cookie
security flags, CORS origins, sandbox resource limits, rate-limit
thresholds. `.env` itself is gitignored; nothing sensitive is ever
hardcoded (`security.md`). `SECRET_KEY` in particular must be generated
fresh per environment before any real deployment:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

`COOKIE_SECURE=true` and `ENVIRONMENT=production` should both be set in any
real deployment — the former makes auth cookies HTTPS-only, the latter
enables the HSTS response header (`security.md`).

## Production Docker targets

Each of the three Dockerfiles (`backend/`, `worker/`, `frontend/`) has a
`production` build target, distinct from the `dev` target `docker-compose.yml`
uses locally (dev targets bind-mount source and run with hot-reload; the
production targets copy the source in and run without a reloader). CI builds
and validates all three production images on every push
(`.github/workflows/ci.yml`, job `docker-build`) — proven to build cleanly,
not just assumed to.

## CI as a deployment gate

`.github/workflows/ci.yml` runs backend/worker/frontend lint+type-check+test,
builds all three production images, and — the most complete check — brings
up the real `docker-compose.yml` stack on a fresh runner, runs the database
migration, and runs the Playwright golden-path test against it end to end.
A green CI run is a genuine signal that the full pipeline (register → create
project → write code → run it in a real sandboxed container → see the
result) works, not just that each piece compiles in isolation.
