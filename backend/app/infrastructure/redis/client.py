import asyncio
import weakref
from typing import cast

from redis.asyncio import Redis

from app.core.config import get_settings

# Keyed by event loop (WeakKeyDictionary, not id(loop), which can recycle):
# redis-py connections are loop-bound, so a plain singleton goes stale
# under pytest-asyncio's per-test loops.
type _ClientMap = weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Redis]
_clients: _ClientMap = weakref.WeakKeyDictionary()


def get_redis() -> Redis:
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        settings = get_settings()
        client = cast(
            Redis,
            Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                # Detects a connection silently dropped by Docker's network
                # while idle — otherwise commands like PUBLISH report success
                # but reach no one.
                health_check_interval=30,
                socket_keepalive=True,
            ),
        )
        _clients[loop] = client
    return client
