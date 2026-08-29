from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import database_connection_errors, queue_depth
from app.infrastructure.database.session import get_db
from app.infrastructure.redis.client import get_redis
from app.infrastructure.redis.streams import EXECUTION_STREAM_KEY
from app.schemas.envelope import Envelope

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=Envelope[dict[str, Any]])
async def health() -> Envelope[dict[str, Any]]:
    """Liveness probe: process is up and able to serve requests."""
    return Envelope(data={"status": "ok"})


@router.get("/ready", response_model=Envelope[dict[str, Any]], status_code=status.HTTP_200_OK)
async def ready(db: AsyncSession = Depends(get_db)) -> Envelope[dict[str, Any]]:
    """Readiness probe: verifies required dependencies (Postgres, Redis) are reachable."""
    checks: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness must report, never crash
        logger.warning("readiness_check_failed", dependency="database", error=str(exc))
        checks["database"] = "unavailable"
        database_connection_errors.inc()

    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="redis", error=str(exc))
        checks["redis"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return Envelope(data={"status": "ok" if all_ok else "degraded", "checks": checks})


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape endpoint. Deliberately outside the {data,error} envelope —
    the exposition format is plain text, not JSON, and Prometheus doesn't unwrap it."""
    try:
        redis = get_redis()
        queue_depth.set(await redis.xlen(EXECUTION_STREAM_KEY))
    except Exception as exc:  # noqa: BLE001 - a stale gauge beats a broken scrape
        logger.warning("metrics_queue_depth_unavailable", error=str(exc))

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
