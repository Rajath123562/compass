import asyncio
from contextlib import asynccontextmanager


class LockManager:
    """Global lock manager for workflow orchestration. Prevents AB-BA deadlocks."""

    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_or_create_lock(self, name: str) -> asyncio.Lock:
        async with self._global_lock:
            if name not in self._locks:
                self._locks[name] = asyncio.Lock()
            return self._locks[name]

    @asynccontextmanager
    async def acquire_locks(self, lock_names: list[str]):
        """Acquires a set of locks safely by sorting them alphabetically first."""
        if not lock_names:
            yield
            return

        sorted_names = sorted(set(lock_names))
        acquired_locks = []

        try:
            for name in sorted_names:
                l = await self._get_or_create_lock(name)
                await l.acquire()
                acquired_locks.append(l)

            yield

        finally:
            # Release in reverse order
            for l in reversed(acquired_locks):
                l.release()


class Scheduler:
    """Schedules ready nodes based on priority and concurrency limits."""

    def __init__(self, lock_manager: LockManager, max_concurrent: int = 5):
        self.lock_manager = lock_manager
        self.max_concurrent = max_concurrent
        self.active_nodes: set[str] = set()

    def can_schedule(self, node_id: str) -> bool:
        if len(self.active_nodes) >= self.max_concurrent:  # noqa: SIM103
            return False
        return True

    def mark_scheduled(self, node_id: str):
        self.active_nodes.add(node_id)

    def mark_completed(self, node_id: str):
        if node_id in self.active_nodes:
            self.active_nodes.remove(node_id)


# Re-export Phase 8 workflow scheduler symbols
from planner.workflow_scheduler import *  # noqa: F401, F403
