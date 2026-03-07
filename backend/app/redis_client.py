"""Redis client for caching and session memory.

This module is intentionally resilient: if Redis is down, the app will continue
to run (cache becomes a no-op) instead of crashing request handling.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class _InMemoryCache:
    """Very small in-process cache fallback.

    This is a development convenience when Redis isn't running. It is not
    shared across processes and is cleared on restart.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and time.time() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        expires_at = (time.time() + int(ex)) if ex is not None else None
        self._store[key] = (value, expires_at)
        return True

    def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if k in self._store:
                self._store.pop(k, None)
                removed += 1
        return removed


class RedisFacade:
    """Small wrapper around redis-py that never raises to callers."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._fallback = _InMemoryCache()
        self._client: redis.Redis | None = None
        self._connected: bool | None = None
        if (url or "").strip():
            self._client = redis.from_url(url, decode_responses=True)
        self._warned_down = False

    def health(self) -> dict:
        """Return a small health payload for API diagnostics."""

        backend = "redis" if self._client is not None else "memory"
        return {
            "ok": True,
            "backend": backend,
            # True only when an actual Redis server is reachable.
            "connected": bool(self._connected) if self._connected is not None else False,
            "url": self._url,
        }

    def _warn_down(self, message: str, **fields: str) -> None:
        if self._warned_down:
            return
        self._warned_down = True
        payload = {"url": self._url, **fields}
        logger.warning(message, extra={"extra": payload})

    async def ping(self) -> bool:
        if self._client is None:
            # Cache still works via in-memory fallback.
            self._connected = False
            return True
        try:
            res = await self._client.ping()
            self._connected = True
            return bool(res)
        except Exception as e:
            # If Redis isn't reachable, switch to in-memory fallback for the
            # remainder of this process. (If you start Redis later, restart the
            # backend to re-enable Redis.)
            self._client = None
            self._connected = False
            self._warn_down("Redis unavailable; using in-memory cache fallback", err=str(e))
            return True

    async def get(self, key: str) -> Optional[str]:
        if self._client is None:
            return self._fallback.get(key)
        try:
            return await self._client.get(key)
        except Exception as e:
            self._client = None
            self._connected = False
            self._warn_down("Redis unavailable; using in-memory cache fallback", err=str(e), op="get")
            return self._fallback.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        if self._client is None:
            return self._fallback.set(key, value, ex=ex)
        try:
            res = await self._client.set(key, value, ex=ex)
            return bool(res)
        except Exception as e:
            self._client = None
            self._connected = False
            self._warn_down("Redis unavailable; using in-memory cache fallback", err=str(e), op="set")
            return self._fallback.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> int:
        if self._client is None:
            return self._fallback.delete(*keys)
        try:
            if not keys:
                return 0
            res = await self._client.delete(*keys)
            return int(res or 0)
        except Exception as e:
            self._client = None
            self._connected = False
            self._warn_down("Redis unavailable; using in-memory cache fallback", err=str(e), op="delete")
            return self._fallback.delete(*keys)

    async def close(self) -> None:
        if self._client is None:
            return
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
