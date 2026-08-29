from typing import cast

from redis.asyncio import Redis

from config import get_worker_settings


def create_redis_client() -> Redis:
    settings = get_worker_settings()
    return cast(
        Redis,
        Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=30,
            # This connection lives for the worker's whole lifetime and mostly sits idle
            # between jobs (XREADGROUP naturally cycles on its own block timeout, but the
            # publish() call in execution_manager.py reuses this same connection and can go
            # a long time between uses). An idle connection silently dropped by Docker's
            # bridge network looks fine to redis-py — publish() returns without error but
            # never reaches the server. A periodic PING here catches that and reconnects
            # before it's relied on. Confirmed live: a worker left running for a while had
            # publish() consistently report 0 subscribers despite an active SSE listener,
            # and a fresh connection immediately fixed it.
            health_check_interval=30,
            socket_keepalive=True,
        ),
    )
