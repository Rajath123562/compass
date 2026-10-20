import asyncio

import pytest

from planner.workflow.scheduler import LockManager, Scheduler


@pytest.mark.asyncio
async def test_lock_manager_ab_ba():
    lm = LockManager()

    # We will try to acquire A then B in task 1, and B then A in task 2.
    # The LockManager sorts them automatically so it avoids deadlock.

    results = []

    async def worker_1():
        async with lm.acquire_locks(["A", "B"]):
            results.append(1)
            await asyncio.sleep(0.01)

    async def worker_2():
        async with lm.acquire_locks(["B", "A"]):
            results.append(2)
            await asyncio.sleep(0.01)

    await asyncio.gather(worker_1(), worker_2())

    assert len(results) == 2
    assert set(results) == {1, 2}


def test_scheduler_concurrency():
    lm = LockManager()
    scheduler = Scheduler(lock_manager=lm, max_concurrent=2)

    assert scheduler.can_schedule("N1")
    scheduler.mark_scheduled("N1")

    assert scheduler.can_schedule("N2")
    scheduler.mark_scheduled("N2")

    # Limit reached
    assert not scheduler.can_schedule("N3")

    scheduler.mark_completed("N1")
    assert scheduler.can_schedule("N3")
