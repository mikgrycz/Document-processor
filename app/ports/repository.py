"""Persistence interface for jobs.

Any implementation (in-memory, SQL, ...) must satisfy this Protocol so the
application layer never depends on a concrete storage technology.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.models import Job


class JobRepository(Protocol):
    async def add(self, job: Job) -> None:
        """Persist a new job."""
        ...

    async def get(self, job_id: str) -> Job | None:
        """Fetch a job by id, or None if it doesn't exist."""
        ...

    async def get_by_idempotency_key(self, key: str) -> Job | None:
        """Fetch a job previously submitted with the given idempotency key."""
        ...

    async def update(self, job: Job) -> None:
        """Persist changes made to an existing job."""
        ...
