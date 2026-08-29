"""Prometheus metrics for the API process.

http_requests_total and http_request_duration_seconds are recorded by
MetricsMiddleware for every request. The rest are incremented from the
specific application code that knows about that event (execution creation,
rate-limit rejection, a failed readiness check) — see each metric's call
site for where it's touched.
"""

from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests handled",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

execution_total = Counter(
    "execution_total",
    "Total executions created and enqueued",
)

queue_depth = Gauge(
    "queue_depth",
    "Current length of the execution job stream (jobs not yet consumed by a worker)",
)

database_connection_errors = Counter(
    "database_connection_errors",
    "Total database connection failures observed by the readiness check",
)

rate_limit_rejections_total = Counter(
    "rate_limit_rejections_total",
    "Total requests rejected by rate limiting",
    ["scope"],
)
