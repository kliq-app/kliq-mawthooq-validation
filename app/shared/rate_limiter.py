from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Optional

from app.shared.settings import settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_sec: int) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - window_sec
        async with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    async def reset(self) -> None:
        async with self._lock:
            self._buckets.clear()


class RedisRateLimiter:
    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(redis_url, decode_responses=True)

    async def allow(self, key: str, limit: int, window_sec: int) -> bool:
        if limit <= 0:
            return True
        now = time.time()
        key_name = f"rate:{key}"
        script = (
            "local key = KEYS[1] "
            "local now = tonumber(ARGV[1]) "
            "local window = tonumber(ARGV[2]) "
            "local limit = tonumber(ARGV[3]) "
            "redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window) "
            "redis.call('ZADD', key, now, now) "
            "local count = redis.call('ZCARD', key) "
            "redis.call('EXPIRE', key, window + 1) "
            "return count"
        )
        count = await self._client.eval(script, 1, key_name, now, window_sec, limit)
        if count > limit:
            await self._client.zrem(key_name, str(now))
            return False
        return True


class RateLimiter:
    def __init__(self, redis_url: Optional[str]) -> None:
        self._memory = InMemoryRateLimiter()
        self._redis: Optional[RedisRateLimiter] = None
        if redis_url:
            try:
                self._redis = RedisRateLimiter(redis_url)
            except Exception:
                self._redis = None

    async def allow(self, key: str, limit: int, window_sec: int) -> bool:
        if self._redis:
            try:
                return await self._redis.allow(key, limit, window_sec)
            except Exception:
                return await self._memory.allow(key, limit, window_sec)
        return await self._memory.allow(key, limit, window_sec)

    async def reset(self) -> None:
        await self._memory.reset()


rate_limiter = RateLimiter(settings.redis_url)
