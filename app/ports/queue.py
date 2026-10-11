"""Work queue interface decoupling job submission from job processing."""

from __future__ import annotations

from typing import Protocol


class JobQueue(Protocol):
    async def enqueue(self, job_id: str) -> None:
        """Schedule a job id for processing."""
        ...

    async def dequeue(self) -> str:
        """Wait for and return the next job id to process."""
        ...

    def depth(self) -> int:
        """Return the number of job ids currently waiting to be processed."""
        ...
