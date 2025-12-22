from __future__ import annotations

import asyncio
import time


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_seconds: int) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.reset_seconds = max(1, reset_seconds)
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            if self._opened_at is None:
                return True
            if time.monotonic() - self._opened_at >= self.reset_seconds:
                self._opened_at = None
                self._failure_count = 0
                return True
            return False

    async def record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.monotonic()

    async def reset(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._opened_at = None

    async def configure(self, failure_threshold: int, reset_seconds: int) -> None:
        async with self._lock:
            self.failure_threshold = max(1, failure_threshold)
            self.reset_seconds = max(1, reset_seconds)
            self._failure_count = 0
            self._opened_at = None
