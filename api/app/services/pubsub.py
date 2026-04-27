import asyncio
from collections import defaultdict
from uuid import UUID


class AlertBroker:
    def __init__(self) -> None:
        self._queues: dict[UUID, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, owner_id: UUID) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._queues[owner_id].append(q)
        return q

    async def unsubscribe(self, owner_id: UUID, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._queues[owner_id]:
                self._queues[owner_id].remove(q)

    async def publish(self, owner_id: UUID, payload: dict) -> None:
        async with self._lock:
            qs = list(self._queues.get(owner_id, []))
        for q in qs:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


broker = AlertBroker()
