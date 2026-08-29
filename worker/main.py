"""CodeForge execution worker entrypoint.

Consumes execution jobs from the Redis Stream the API publishes to, runs each
one inside an isolated Docker sandbox container, and writes the result back to
Postgres. See consumer.py for delivery semantics and execution_manager.py for
per-job handling.
"""

import asyncio
import signal
import sys

import docker
import structlog
from prometheus_client import start_http_server

from config import get_worker_settings
from consumer import StreamConsumer
from execution_manager import ExecutionManager
from logging_config import configure_logging
from redis_client import create_redis_client

METRICS_PORT = 9100

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main() -> None:
    settings = get_worker_settings()
    configure_logging(service_name="execution-worker", log_level=settings.log_level)
    logger = structlog.get_logger(__name__)

    logger.info(
        "worker_startup",
        environment=settings.environment,
        stream=settings.stream_key,
        consumer=settings.consumer_name,
    )

    # start_http_server runs its own background thread, independent of this
    # process's asyncio loop, so it doesn't need to be awaited or shut down
    # explicitly — it dies with the process.
    start_http_server(METRICS_PORT)
    logger.info("metrics_server_started", port=METRICS_PORT)

    docker_client = docker.DockerClient(base_url=f"unix://{settings.docker_socket}")
    redis_client = create_redis_client()
    manager = ExecutionManager(settings, docker_client, redis_client)
    consumer = StreamConsumer(redis_client, settings, manager)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, consumer.request_shutdown)
        except NotImplementedError:
            # add_signal_handler is POSIX-only; fall back for local Windows runs.
            signal.signal(sig, lambda _signum, _frame: consumer.request_shutdown())

    try:
        await consumer.run()
    finally:
        await redis_client.aclose()
        docker_client.close()
        logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
