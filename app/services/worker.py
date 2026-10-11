"""Async worker: pulls job ids off the queue and runs them to completion.

Transient failures are re-enqueued with backoff until max_attempts is hit;
permanent or unexpected failures fail the job right away.
"""

from __future__ import annotations

import asyncio
import time

from app.domain.errors import PermanentProcessingError, TransientProcessingError
from app.domain.models import Job, JobStatus
from app.observability.logging import get_logger
from app.observability.metrics import job_duration_seconds, job_retries_total, jobs_completed_total
from app.ports.fetcher import DocumentFetcher
from app.ports.queue import JobQueue
from app.ports.repository import JobRepository
from app.processors.registry import get_processor
from app.services.retry import RetryPolicy, SleepFn

logger = get_logger(__name__)


async def _default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


class Worker:
    def __init__(
        self,
        repository: JobRepository,
        queue: JobQueue,
        fetcher: DocumentFetcher,
        retry_policy: RetryPolicy | None = None,
        sleep: SleepFn = _default_sleep,
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._fetcher = fetcher
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    async def run_forever(self) -> None:
        """Continuously dequeue and process jobs until cancelled."""
        while True:
            job_id = await self._queue.dequeue()
            await self.process_one(job_id)

    async def resync(self) -> None:
        """Re-enqueue jobs left queued or running by a previous process.

        Running jobs are reset to queued first, since no worker is
        actually processing them anymore.
        """
        for job in await self._repository.list_active():
            if job.status is JobStatus.RUNNING:
                job.retry("resynced after restart")
                await self._repository.update(job)
            await self._queue.enqueue(job.id)

    async def process_one(self, job_id: str) -> None:
        """Process a single job id to a terminal or requeued state."""
        job = await self._repository.get(job_id)
        if job is None:
            logger.warning("job_not_found", job_id=job_id)
            return

        job.start()
        await self._repository.update(job)
        logger.info(
            "job_started", job_id=job.id, operation=job.operation.value, attempt=job.attempts
        )
        started_at = time.monotonic()

        try:
            data = await self._fetcher.fetch(job.document_url)
            processor = get_processor(job.operation)
            result = await processor(data)
        except PermanentProcessingError as exc:
            job.fail(f"permanent: {exc}")
            await self._finish(job, started_at)
            logger.warning("job_failed", job_id=job.id, reason="permanent", error=str(exc))
        except TransientProcessingError as exc:
            await self._handle_transient_failure(job, f"transient: {exc}", started_at)
        except Exception as exc:  # noqa: BLE001
            logger.exception("job_unexpected_error", job_id=job.id)
            job.fail(f"unexpected: {exc}")
            await self._finish(job, started_at)
        else:
            job.succeed(result)
            await self._finish(job, started_at)
            logger.info("job_succeeded", job_id=job.id, attempt=job.attempts)

    async def _handle_transient_failure(self, job: Job, error: str, started_at: float) -> None:
        if job.can_retry:
            job.retry(error)
            await self._repository.update(job)
            job_retries_total.inc()
            job_duration_seconds.observe(time.monotonic() - started_at)
            logger.info("job_retry_scheduled", job_id=job.id, attempt=job.attempts, error=error)
            await self._sleep(self._retry_policy.delay_for_attempt(job.attempts))
            await self._queue.enqueue(job.id)
        else:
            job.fail(error)
            await self._finish(job, started_at)
            logger.warning("job_failed", job_id=job.id, reason="retries_exhausted", error=error)

    async def _finish(self, job: Job, started_at: float) -> None:
        """Persist a terminal job state and record its metrics."""
        await self._repository.update(job)
        job_duration_seconds.observe(time.monotonic() - started_at)
        jobs_completed_total.labels(status=job.status.value).inc()
