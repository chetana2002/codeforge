import asyncio
import os
import sys

# Must run before anything under app.* is imported — app.core.config reads
# env vars at import time, and the event-loop policy must be set before any
# loop is created.
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
# httpx's ASGI test transport never reports a client disconnect, so keep
# these short or an abandoned SSE test blocks later teardown.
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

# Sync client for teardown only: no event-loop affinity, unlike the app's
# async client, so it's safe to reuse across every test's own loop.
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
    """Runs synchronously — sidesteps pytest-asyncio's per-test loop scope."""
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
