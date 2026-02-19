"""Database engine layer for the Macro Trading system.

Provides async engine (asyncpg) for application runtime (FastAPI, connectors)
and sync engine (psycopg2) for Alembic migrations and one-off scripts.
Session factories are configured with autoflush=False and expire_on_commit=False
for explicit transaction control.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

# ---------------------------------------------------------------------------
# Async engine (for application runtime -- asyncpg)
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    echo=settings.debug,
)

# Async session factory
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Sync engine (for Alembic, seeds, one-off scripts -- psycopg2)
# ---------------------------------------------------------------------------
sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=5,
    pool_pre_ping=True,
    echo=settings.debug,
)

# Sync session factory
sync_session_factory = sessionmaker(
    sync_engine,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Dependency injectors
# ---------------------------------------------------------------------------
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Usage::

        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_async_session)):
            ...

    The session is automatically rolled back on unhandled exceptions and
    closed when the request finishes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_sync_session() -> Session:
    """Get a sync session for scripts and migrations.

    Caller is responsible for closing the session::

        session = get_sync_session()
        try:
            ...
        finally:
            session.close()
    """
    return sync_session_factory()
