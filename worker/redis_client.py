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
            # Detects a connection silently dropped by Docker's network while idle
            # between jobs — otherwise publish() reports success but reaches no one.
            health_check_interval=30,
            socket_keepalive=True,
        ),
    )
