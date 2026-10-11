"""In-memory implementation of the JobRepository port.

Swapping in a durable store (e.g. Postgres) means implementing the same
Protocol defined in app/ports/repository.py — no changes needed in
JobService or above.
"""

from __future__ import annotations

from app.domain.models import Job, JobStatus


class InMemoryJobRepository:
    """Stores jobs in a plain dict, keyed by id, with an idempotency-key index."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._by_idempotency_key: dict[str, str] = {}

    async def add(self, job: Job) -> None:
        self._jobs[job.id] = job
        if job.idempotency_key is not None:
            self._by_idempotency_key[job.idempotency_key] = job.id

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def get_by_idempotency_key(self, key: str) -> Job | None:
        job_id = self._by_idempotency_key.get(key)
        return self._jobs.get(job_id) if job_id is not None else None

    async def update(self, job: Job) -> None:
        self._jobs[job.id] = job

    async def list_active(self) -> list[Job]:
        return [
            job
            for job in self._jobs.values()
            if job.status in (JobStatus.QUEUED, JobStatus.RUNNING)
        ]
