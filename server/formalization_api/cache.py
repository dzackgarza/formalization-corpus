from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(slots=True)
class CacheEntry:
    body: bytes
    expires_at: float


class ByteLRUTTLCache:
    """A bounded in-memory LRU cache measured by response bytes."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_bytes: int,
        max_entry_bytes: int,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_bytes = max_bytes
        self.max_entry_bytes = max_entry_bytes
        self.max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._bytes = 0
        self._lock = asyncio.Lock()

    @property
    def bytes_used(self) -> int:
        return self._bytes

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    async def get(self, key: str) -> bytes | None:
        now = self._clock()
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._delete(key)
                return None
            self._entries.move_to_end(key)
            return entry.body

    async def put(self, key: str, body: bytes) -> bool:
        size = len(body)
        if size > self.max_entry_bytes or size > self.max_bytes:
            return False

        async with self._lock:
            if key in self._entries:
                self._delete(key)

            while self._entries and (
                self._bytes + size > self.max_bytes
                or len(self._entries) >= self.max_entries
            ):
                oldest, _ = next(iter(self._entries.items()))
                self._delete(oldest)

            self._entries[key] = CacheEntry(
                body=body,
                expires_at=self._clock() + self.ttl_seconds,
            )
            self._bytes += size
            return True

    def _delete(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._bytes -= len(entry.body)


class SingleFlight:
    """Coalesce simultaneous cache misses for the same normalized request."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[bytes]] = {}
        self._lock = asyncio.Lock()

    async def _run_producer(
        self,
        key: str,
        producer: Callable[[], Awaitable[bytes]],
    ) -> bytes:
        try:
            return await producer()
        finally:
            task = asyncio.current_task()
            async with self._lock:
                if self._tasks.get(key) is task:
                    self._tasks.pop(key, None)

    async def run(
        self,
        key: str,
        producer: Callable[[], Awaitable[bytes]],
    ) -> tuple[bytes, bool]:
        async with self._lock:
            task = self._tasks.get(key)
            leader = task is None
            if task is None:
                task = asyncio.create_task(self._run_producer(key, producer))
                self._tasks[key] = task

        # A disconnected/cancelled caller must not cancel or unregister the shared
        # producer.  The producer owns cleanup when it actually finishes, so a
        # retry can still join the same in-flight backend search.
        return await asyncio.shield(task), leader
