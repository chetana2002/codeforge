"""Prometheus metrics for the execution worker.

Exposed on a plain HTTP server on port 9100 via start_http_server() (called
from main.py) — the worker has no other HTTP server, so this doesn't share a
port or ASGI app with anything else. worker_jobs_total / worker_job_failures_total
track the consumer's own delivery loop (see consumer.py); the execution_*
metrics track outcomes of the jobs it hands off to ExecutionManager.
"""

from prometheus_client import Counter, Histogram

worker_jobs_total = Counter(
    "worker_jobs_total",
    "Total execution jobs the worker has picked up off the stream",
)

worker_job_failures_total = Counter(
    "worker_job_failures_total",
    "Total jobs that raised an unexpected exception (left un-ACKed for retry)",
)

execution_success_total = Counter(
    "execution_success_total",
    "Total executions that completed successfully",
)

execution_failure_total = Counter(
    "execution_failure_total",
    "Total executions that ended failed, timed out, or were cancelled",
)

execution_duration_seconds = Histogram(
    "execution_duration_seconds",
    "Sandbox execution duration in seconds, from container start to exit",
)
