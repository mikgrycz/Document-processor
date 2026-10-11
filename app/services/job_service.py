"""Application service orchestrating job submission and retrieval.

This is the orchestration layer: it depends only on the ports (Protocols),
never on concrete adapters or the web framework, so it can be exercised in
tests with fakes and reused behind any transport.
"""

from __future__ import annotations

import asyncio
import hashlib

from app.domain.models import Job, Operation
from app.observability.logging import get_logger
from app.observability.metrics import jobs_submitted_total
from app.ports.queue import JobQueue
from app.ports.repository import JobRepository

logger = get_logger(__name__)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with a different payload.

    Assumption: the idempotency key is optional and its scope is global
    (not per-client). Reusing a key with the same document_url and
    operation returns the original job; reusing it with a different
    payload is treated as a client error.
    """

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"idempotency key '{idempotency_key}' was already used with a different request"
        )
        self.idempotency_key = idempotency_key


class JobService:
    """Orchestrates job submission, idempotency, and lookup."""

    def __init__(self, repository: JobRepository, queue: JobQueue) -> None:
        self._repository = repository
        self._queue = queue
        # Serializes submit() so the idempotency-key check-and-insert is
        # atomic. Sufficient for a single-process, in-memory timebox; a
        # durable store would instead rely on a unique constraint on
        # idempotency_key plus a transaction.
        self._submit_lock = asyncio.Lock()

    async def submit(
        self,
        document_url: str,
        operation: Operation,
        idempotency_key: str | None = None,
    ) -> tuple[Job, bool]:
        """Submit a job for processing.

        Returns ``(job, created)`` where ``created`` is False when an
        existing job for the same idempotency key was returned instead of
        a new one being created.
        """
        async with self._submit_lock:
            if idempotency_key is not None:
                existing = await self._repository.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    if existing.document_url != document_url or existing.operation != operation:
                        logger.warning(
                            "idempotency_conflict", idempotency_key_hash=_hash_key(idempotency_key)
                        )
                        raise IdempotencyConflictError(idempotency_key)
                    logger.info("job_submit_replayed", job_id=existing.id)
                    return existing, False

            job = Job(
                document_url=document_url,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            await self._repository.add(job)
            await self._queue.enqueue(job.id)
            jobs_submitted_total.labels(operation=operation.value).inc()
            logger.info("job_submitted", job_id=job.id, operation=operation.value)
            return job, True

    async def get(self, job_id: str) -> Job | None:
        return await self._repository.get(job_id)
