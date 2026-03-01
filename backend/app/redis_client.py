"""Redis client for caching and session memory.

This module is intentionally resilient: if Redis is down, the app will continue
to run (cache becomes a no-op) instead of crashing request handling.
"""

from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisFacade:
    """Small wrapper around redis-py that never raises to callers."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: redis.Redis = redis.from_url(url, decode_responses=True)
        self._warned_down = False

    def _warn_down(self, message: str, **fields: str) -> None:
        if self._warned_down:
            return
        self._warned_down = True
        payload = {"url": self._url, **fields}
        logger.warning(message, extra={"extra": payload})

    async def ping(self) -> bool:
        try:
            res = await self._client.ping()
            return bool(res)
        except Exception as e:
            self._warn_down("Redis unavailable; continuing without cache", err=str(e))
            return False

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self._client.get(key)
        except Exception as e:
            self._warn_down("Redis unavailable; continuing without cache", err=str(e), op="get")
            return None

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        try:
            res = await self._client.set(key, value, ex=ex)
            return bool(res)
        except Exception as e:
            self._warn_down("Redis unavailable; continuing without cache", err=str(e), op="set")
            return False

    async def delete(self, *keys: str) -> int:
        try:
            if not keys:
                return 0
            res = await self._client.delete(*keys)
            return int(res or 0)
        except Exception as e:
            self._warn_down("Redis unavailable; continuing without cache", err=str(e), op="delete")
            return 0

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            return


_redis_singleton: Optional[RedisFacade] = None


def get_redis() -> RedisFacade:
    """Return a singleton Redis client facade."""

    global _redis_singleton
    if _redis_singleton is None:
        _redis_singleton = RedisFacade(settings.redis_url)
    return _redis_singleton
