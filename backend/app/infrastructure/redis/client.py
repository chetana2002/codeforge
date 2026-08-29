import asyncio
import weakref
from typing import cast

from redis.asyncio import Redis

from app.core.config import get_settings

# Keyed by the running event loop object itself (via a WeakKeyDictionary, not id(loop))
# rather than a single process-wide singleton: redis-py's async connections are bound to
# the loop they were opened on, so a plain @lru_cache'd client goes stale the moment it's
# reused from a different loop (e.g. pytest-asyncio, which gives each test its own loop).
# A WeakKeyDictionary is required here rather than a plain dict keyed by id(loop): once a
# loop is garbage-collected, CPython is free to reuse its memory address for a new loop
# object, which would make an id()-keyed dict return a stale, dead client under a
# completely unrelated loop. Weak-keying ties each entry to the loop's actual identity and
# lifetime, and evicts automatically when the loop is collected.
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
                # Without this, a connection idle long enough to be silently dropped by
                # Docker's bridge network (or any NAT in between) looks perfectly healthy
                # to redis-py — the write succeeds locally, the peer never sees it, and
                # commands like PUBLISH return no error while doing nothing. A periodic
                # PING here detects that and swaps in a fresh connection before it's
                # relied on. Confirmed via the SSE endpoint's own long-lived subscribe
                # connection during Phase 12 debugging.
                health_check_interval=30,
                socket_keepalive=True,
            ),
        )
        _clients[loop] = client
    return client
