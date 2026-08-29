import asyncio
import os
import sys

# Must run before anything under app.* is imported: app.core.config reads DATABASE_URL /
# REDIS_URL / SECRET_KEY at import time, and app.core.platform's Windows event-loop fix
# needs to be in effect before any event loop (including pytest-asyncio's) is created.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://codeforge:codeforge_dev_password@localhost:5435/codeforge_test",
)
# DB index 1 (not 0, used by dev) keeps test runs from polluting dev Redis state.
os.environ.setdefault("REDIS_URL", "redis://localhost:6381/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("COOKIE_SECURE", "false")
# httpx's ASGI test transport never reports a disconnect for a client that simply
# stops reading (confirmed empirically — see the comment on stream_execution), so
# an abandoned SSE test would otherwise hold its generator's DB session open for
# the full production default (120s), blocking other tests' schema teardown.
os.environ.setdefault("EXECUTION_STREAM_MAX_SECONDS", "3")
os.environ.setdefault("EXECUTION_STREAM_KEEPALIVE_SECONDS", "1")

from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
import redis as sync_redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import AsyncSessionLocal, engine
from app.main import app

_ADMIN_DATABASE_URL = "postgresql://codeforge:codeforge_dev_password@localhost:5435/codeforge"

# A sync client for test cleanup only: unlike the app's async Redis client (which is
# bound to whichever event loop created it — see app/infrastructure/redis/client.py),
# a sync client has no event-loop affinity, so it can safely be reused across every
# test's teardown regardless of that test's (short-lived, pytest-asyncio-managed) loop.
_sync_redis = sync_redis.Redis.from_url(
    os.environ["REDIS_URL"], decode_responses=True, socket_connect_timeout=5, socket_timeout=5
)


def _ensure_test_database_exists() -> None:
    with psycopg.connect(_ADMIN_DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'codeforge_test'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE codeforge_test")


@pytest.fixture(scope="session", autouse=True)
def _prepare_database() -> Iterator[None]:
    """Schema setup runs synchronously so it needs no event loop at all, sidestepping
    any pytest-asyncio session-vs-function loop scope mismatch with per-test fixtures."""
    _ensure_test_database_exists()
    sync_engine = create_engine(get_settings().database_url)
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)
    sync_engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    _sync_redis.flushdb()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
