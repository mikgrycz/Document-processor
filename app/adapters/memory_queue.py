"""In-memory FIFO job queue backed by asyncio.Queue.

Swapping for a durable broker (Redis, SQS, ...) means implementing the same
Protocol defined in app/ports/queue.py.
"""

from __future__ import annotations

import asyncio


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self) -> str:
        return await self._queue.get()

    def depth(self) -> int:
        return self._queue.qsize()
