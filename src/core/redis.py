"""Redis async client singleton for the Macro Trading system.

Provides a module-level singleton Redis client backed by a ConnectionPool.
The pool lifecycle is managed independently from the client to avoid
premature pool closure (per redis-py Pitfall 5 from RESEARCH.md).

Usage::

    from src.core.redis import get_redis, close_redis

    redis = await get_redis()
    await redis.set("key", "value")
    value = await redis.get("key")

    # During application shutdown:
    await close_redis()
"""

import redis.asyncio as aioredis

from .config import settings

# Module-level globals -- singleton pattern
_redis_pool: aioredis.ConnectionPool | None = None
_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get the singleton async Redis client.

    Creates the connection pool and client on first call. Subsequent calls
    return the same client instance. The pool uses ``decode_responses=True``
    so all values are returned as strings (important for caching JSON).
    """
    global _redis_pool, _redis_client
    if _redis_client is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
        # Use connection_pool= parameter (NOT from_pool()) so the pool
        # lifecycle is managed independently from the client.
        _redis_client = aioredis.Redis(connection_pool=_redis_pool)
    return _redis_client


async def close_redis() -> None:
    """Close Redis client and pool. Call during application shutdown.

    Safe to call multiple times. After calling, ``get_redis()`` will create
    a fresh client on next invocation.
    """
    global _redis_pool, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
