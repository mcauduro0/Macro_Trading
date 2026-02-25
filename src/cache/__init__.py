"""Cache package for the Macro Trading system.

Exports:
- ``PMSCache`` -- Redis-backed cache for PMS endpoints with tiered TTLs
- ``get_pms_cache`` -- FastAPI async dependency returning a PMSCache instance
"""

from src.cache.pms_cache import PMSCache
from src.core.redis import get_redis


async def get_pms_cache() -> PMSCache:
    """FastAPI dependency that returns a :class:`PMSCache` instance.

    Usage in route handlers::

        @router.get("/some-endpoint")
        async def handler(cache: PMSCache = Depends(get_pms_cache)):
            ...
    """
    redis = await get_redis()
    return PMSCache(redis)


__all__ = ["PMSCache", "get_pms_cache"]
