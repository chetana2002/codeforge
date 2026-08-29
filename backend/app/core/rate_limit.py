"""Redis-backed fixed-window rate limiting.

Atomic INCR per (scope, identifier, window) — no GET-then-SET race. Fixed
windows can let up to 2x the limit through at a window boundary, an accepted
tradeoff for abuse-blunting rather than billing-grade quotas. Fails open on
Redis errors — see docs/failure-scenarios.md.
"""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import Depends, Request
from redis.exceptions import RedisError

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.metrics import rate_limit_rejections_total
from app.domain.models.user import User
from app.infrastructure.redis.client import get_redis
from app.schemas.envelope import ApiError

logger = structlog.get_logger(__name__)


async def _check(scope: str, identifier: str, limit: int, window_seconds: int) -> None:
    redis = get_redis()
    key = f"ratelimit:{scope}:{identifier}"

    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
    except RedisError:
        logger.warning("rate_limit_check_failed_open", scope=scope)
        return

    if count > limit:
        rate_limit_rejections_total.labels(scope=scope).inc()
        ttl = await redis.ttl(key)
        retry_after = max(ttl, 1) if ttl and ttl > 0 else window_seconds
        raise ApiError(
            status_code=429,
            code="RATE_LIMITED",
            message="Too many requests. Please slow down and try again shortly.",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit_by_ip(
    scope: str, limit: int, window_seconds: int = 60
) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        identifier = request.client.host if request.client else "unknown"
        await _check(scope, identifier, limit, window_seconds)

    return dependency


def rate_limit_by_user(
    scope: str, limit: int, window_seconds: int = 60
) -> Callable[[User], Awaitable[None]]:
    async def dependency(current_user: User = Depends(get_current_user)) -> None:
        await _check(scope, str(current_user.id), limit, window_seconds)

    return dependency


def login_rate_limit() -> Callable[[Request], Awaitable[None]]:
    settings = get_settings()
    return rate_limit_by_ip("login", settings.rate_limit_login_per_minute)


def execution_rate_limit() -> Callable[[User], Awaitable[None]]:
    settings = get_settings()
    return rate_limit_by_user("execution", settings.rate_limit_execution_per_minute)


def project_create_rate_limit() -> Callable[[User], Awaitable[None]]:
    settings = get_settings()
    return rate_limit_by_user("project_create", settings.rate_limit_project_create_per_minute)
