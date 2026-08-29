from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# psycopg async driver needs "postgresql+psycopg" (already default) — asyncpg would need a
# different DSN scheme. We standardize on psycopg3's async support across sync/async engines.
_ASYNC_DATABASE_URL = settings.database_url

engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a request-scoped database session."""
    async with AsyncSessionLocal() as session:
        yield session
