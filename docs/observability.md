# Observability

## Health and readiness

- `GET /health` — liveness: is the process up and able to respond at all.
  Never checks a dependency, so an orchestrator doesn't restart a perfectly
  healthy process just because Postgres or Redis is briefly unreachable.
- `GET /ready` — readiness: actually pings Postgres and Redis, returns
  `{"status": "ok" | "degraded", "checks": {...}}`. Use this for load-balancer
  health checks and `depends_on: condition: service_healthy` in orchestration;
  use `/health` for liveness/restart policies.

## Metrics

Both the API (`:8000/metrics`) and the worker (dedicated metrics-only server,
`:9100`) expose Prometheus text-format metrics. Custom metrics, and where
each is recorded:

| Metric | Type | Where | What it answers |
|---|---|---|---|
| `http_requests_total{method,path,status}` | Counter | API, `MetricsMiddleware` | Request volume and error rate by route |
| `http_request_duration_seconds{method,path}` | Histogram | API, `MetricsMiddleware` | Latency distribution (p50/p95/p99 via `histogram_quantile`) by route |
| `execution_total` | Counter | API, on successful enqueue | Executions created, independent of outcome |
| `queue_depth` | Gauge | API, set from live `XLEN` on every `/metrics` scrape | How far behind the workers are right now |
| `database_connection_errors` | Counter | API, `/ready`'s DB check | Postgres connectivity trouble |
| `rate_limit_rejections_total{scope}` | Counter | API, `rate_limit.py` | Abuse/misconfigured-client signal, broken out by which limit (login/execution/project_create) |
| `worker_jobs_total` | Counter | Worker, every message the consumer picks up | Job throughput |
| `worker_job_failures_total` | Counter | Worker, unexpected exceptions only | Worker-side bugs/crashes, *not* deliberate execution failures |
| `execution_success_total` / `execution_failure_total` | Counter | Worker, on terminal state | Outcome mix — `failure` here bundles `FAILED`/`TIMEOUT`/`CANCELLED` |
| `execution_duration_seconds` | Histogram | Worker, sandbox wall-clock time | How long code actually takes to run, for capacity planning |

`http_requests_total`/`http_request_duration_seconds` deliberately label by
the route **template** (`/executions/{execution_id}`), never the resolved
path with a real id in it — using the resolved path would give every
distinct resource its own metric series and grow the cardinality unboundedly
as the number of executions/projects/files grows. The middleware reads
`scope["route"].path` (available only after routing resolves) specifically
to get the template, not `scope["path"]`.

Both middlewares (`MetricsMiddleware` and `SecurityHeadersMiddleware`) are
implemented as raw ASGI middleware rather than Starlette's
`BaseHTTPMiddleware` — the latter buffers through an internal memory stream
with documented interactions with `StreamingResponse` (delayed first-byte
flushing, interference with a request's own disconnect detection), which
would directly undermine the SSE execution-stream endpoint. Wrapping `send`
directly avoids that entirely; see the docstrings on both middleware modules.

## Dashboards

Grafana is provisioned automatically on startup (`infra/grafana/provisioning/`)
with a pinned datasource UID (`prometheus` — set explicitly rather than left
to Grafana's auto-generated one, so dashboard JSON referencing it stays
correct across a fresh volume) and one dashboard, **CodeForge Overview**:
HTTP request rate and p95 latency by route, response codes, rate-limit
rejections by scope, queue depth, execution creation rate, database
connection errors, worker job failures, execution outcome mix, execution
duration percentiles, and worker throughput. All panels were verified
rendering real, non-zero data against live traffic during this project's own
build — not just configured and assumed correct.

## Logging

Structured JSON logs (`structlog`, `app/core/logging.py`) on both API and
worker, with a fixed set of fields per line (`service`, `event`, `level`,
`timestamp`, plus event-specific context) rather than free-text messages —
built to be queried (by event name, by execution id, by user id) rather than
grepped. Known-sensitive key names (passwords, tokens, secrets) are redacted
before a line is ever written, so a value accidentally passed into a log
call doesn't end up in log output verbatim regardless of where in the
codebase it happened.

## What's deliberately not here

No distributed tracing (`OTEL_EXPORTER_OTLP_ENDPOINT` exists as a
configuration placeholder but nothing currently exports to it) — with two
services and a queue in between, structured logs correlated by execution id
cover this project's actual debugging needs without the operational cost of
running a trace collector. This is a real gap at higher service-count scale,
named the same way the other known gaps in this project are (see
`failure-scenarios.md`), not silently omitted.
