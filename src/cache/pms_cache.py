"""Redis caching layer for PMS (Portfolio Management System) endpoints.

Provides tiered TTL caching for all PMS query endpoints with write-through
and cascade invalidation patterns.

TTL tiers (matched to data volatility):
- Book (positions):  30 seconds  -- near real-time
- Risk metrics:      60 seconds  -- moderate update frequency
- Morning pack:     300 seconds  -- generated once per day
- Attribution:      300 seconds  -- compute-heavy, infrequent change

Usage::

    from src.cache import get_pms_cache

    cache = await get_pms_cache()
    book = await cache.get_book()
    if book is None:
        book = compute_book()
        await cache.set_book(book)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default TTLs (seconds) -- tiered by data volatility
# ---------------------------------------------------------------------------
TTL_BOOK = 30  # positions: near real-time
TTL_RISK = 60  # risk metrics: moderate refresh
TTL_MORNING_PACK = 300  # daily briefing: 5 min
TTL_ATTRIBUTION = 300  # compute-heavy analytics: 5 min

# Key prefix for all PMS cache entries
KEY_PREFIX = "pms:"


class PMSCache:
    """Redis-backed cache for PMS endpoints with tiered TTLs.

    Parameters
    ----------
    redis_client : redis.asyncio.Redis
        An async Redis client instance (from ``src.core.redis.get_redis``).
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Book (positions) -- 30s TTL
    # ------------------------------------------------------------------
    async def get_book(self) -> Optional[dict]:
        """Retrieve cached portfolio book, or ``None`` on miss."""
        return await self._get(f"{KEY_PREFIX}book")

    async def set_book(self, data: dict, ttl: int = TTL_BOOK) -> None:
        """Cache portfolio book data with configurable TTL."""
        await self._set(f"{KEY_PREFIX}book", data, ttl)

    # ------------------------------------------------------------------
    # Morning Pack briefing -- 300s TTL
    # ------------------------------------------------------------------
    async def get_morning_pack(self, date_key: str) -> Optional[dict]:
        """Retrieve cached morning-pack for *date_key*, or ``None``."""
        return await self._get(f"{KEY_PREFIX}morning_pack:{date_key}")

    async def set_morning_pack(
        self, date_key: str, data: dict, ttl: int = TTL_MORNING_PACK
    ) -> None:
        """Cache morning-pack briefing for *date_key*."""
        await self._set(f"{KEY_PREFIX}morning_pack:{date_key}", data, ttl)

    # ------------------------------------------------------------------
    # Risk metrics -- 60s TTL
    # ------------------------------------------------------------------
    async def get_risk_metrics(self) -> Optional[dict]:
        """Retrieve cached live risk metrics, or ``None``."""
        return await self._get(f"{KEY_PREFIX}risk:live")

    async def set_risk_metrics(self, data: dict, ttl: int = TTL_RISK) -> None:
        """Cache live risk metrics."""
        await self._set(f"{KEY_PREFIX}risk:live", data, ttl)

    # ------------------------------------------------------------------
    # Attribution -- 300s TTL
    # ------------------------------------------------------------------
    async def get_attribution(self, period_key: str) -> Optional[dict]:
        """Retrieve cached attribution for *period_key*, or ``None``."""
        return await self._get(f"{KEY_PREFIX}attribution:{period_key}")

    async def set_attribution(
        self, period_key: str, data: dict, ttl: int = TTL_ATTRIBUTION
    ) -> None:
        """Cache attribution data for *period_key*."""
        await self._set(f"{KEY_PREFIX}attribution:{period_key}", data, ttl)

    # ------------------------------------------------------------------
    # Write-through helpers
    # ------------------------------------------------------------------
    async def invalidate_portfolio_data(self) -> None:
        """Cascade invalidation: delete book, risk, and all attribution keys.

        Called after any write operation that changes portfolio state
        (position open/close, MTM, trade approval).
        """
        try:
            # Delete deterministic keys
            await self._redis.delete(
                f"{KEY_PREFIX}book",
                f"{KEY_PREFIX}risk:live",
            )
            # Scan and delete all attribution keys (pattern match)
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match=f"{KEY_PREFIX}attribution:*",
                    count=100,
                )
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
            logger.debug("PMSCache: cascade invalidation complete")
        except Exception:
            logger.warning("PMSCache: cascade invalidation failed", exc_info=True)

    async def refresh_book(self, book_data: dict) -> None:
        """Write-through: immediately cache fresh book data after a write.

        Proactive refresh (not just delete) so the next read is instant.
        """
        await self.set_book(book_data)

    async def refresh_risk(self, risk_data: dict) -> None:
        """Write-through: immediately cache fresh risk data after a write."""
        await self.set_risk_metrics(risk_data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _get(self, key: str) -> Optional[dict]:
        """GET a JSON-serialized value from Redis. Returns None on miss or error."""
        try:
            raw = await self._redis.get(key)
            if raw is None:
                logger.debug("PMSCache MISS: %s", key)
                return None
            logger.debug("PMSCache HIT: %s", key)
            return json.loads(raw)
        except Exception:
            logger.warning("PMSCache: GET failed for %s", key, exc_info=True)
            return None

    async def _set(self, key: str, data: dict, ttl: int) -> None:
        """SET a JSON-serialized value in Redis with EX (seconds)."""
        try:
            raw = json.dumps(data, default=str)
            await self._redis.set(key, raw, ex=ttl)
            logger.debug("PMSCache SET: %s (ttl=%ds)", key, ttl)
        except Exception:
            logger.warning("PMSCache: SET failed for %s", key, exc_info=True)
