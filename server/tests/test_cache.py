from __future__ import annotations

import asyncio

from formalization_api.cache import ByteLRUTTLCache, SingleFlight


def test_lru_evicts_by_total_bytes() -> None:
    async def run() -> None:
        cache = ByteLRUTTLCache(
            ttl_seconds=60,
            max_bytes=6,
            max_entry_bytes=6,
            max_entries=10,
        )
        assert await cache.put("a", b"aaa")
        assert await cache.put("b", b"bbb")
        assert await cache.get("a") == b"aaa"  # a is most recently used
        assert await cache.put("c", b"cccc")
        assert await cache.get("b") is None
        assert await cache.get("a") is None
        assert await cache.get("c") == b"cccc"
        assert cache.bytes_used == 4

    asyncio.run(run())


def test_ttl_expiration() -> None:
    async def run() -> None:
        now = [10.0]
        cache = ByteLRUTTLCache(
            ttl_seconds=5,
            max_bytes=100,
            max_entry_bytes=100,
            max_entries=10,
            clock=lambda: now[0],
        )
        await cache.put("a", b"value")
        assert await cache.get("a") == b"value"
        now[0] = 15.0
        assert await cache.get("a") is None
        assert cache.bytes_used == 0

    asyncio.run(run())


def test_oversized_entry_is_not_cached() -> None:
    async def run() -> None:
        cache = ByteLRUTTLCache(
            ttl_seconds=60,
            max_bytes=100,
            max_entry_bytes=4,
            max_entries=10,
        )
        assert not await cache.put("a", b"12345")
        assert await cache.get("a") is None

    asyncio.run(run())


def test_singleflight_coalesces_identical_work() -> None:
    async def run() -> None:
        group = SingleFlight()
        started = 0
        started_event = asyncio.Event()
        release = asyncio.Event()

        async def producer() -> bytes:
            nonlocal started
            started += 1
            started_event.set()
            await release.wait()
            return b"answer"

        tasks = [asyncio.create_task(group.run("same", producer)) for _ in range(8)]
        await started_event.wait()
        assert started == 1
        release.set()
        results = await asyncio.gather(*tasks)
        assert [body for body, _ in results] == [b"answer"] * 8
        assert sum(leader for _, leader in results) == 1

    asyncio.run(run())


def test_singleflight_keeps_inflight_work_after_leader_cancellation() -> None:
    async def run() -> None:
        group = SingleFlight()
        started = 0
        started_event = asyncio.Event()
        release = asyncio.Event()

        async def producer() -> bytes:
            nonlocal started
            started += 1
            started_event.set()
            await release.wait()
            return b"answer"

        leader = asyncio.create_task(group.run("same", producer))
        await started_event.wait()
        leader.cancel()
        try:
            await leader
        except asyncio.CancelledError:
            pass

        follower = asyncio.create_task(group.run("same", producer))
        await asyncio.sleep(0)
        assert started == 1
        release.set()
        body, is_leader = await follower
        assert body == b"answer"
        assert not is_leader

        # Once the shared producer itself has finished, the key is reusable.
        await asyncio.sleep(0)
        body, is_leader = await group.run("same", producer)
        assert body == b"answer"
        assert is_leader
        assert started == 2

    asyncio.run(run())
