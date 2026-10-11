"""Async worker: pulls job ids off the queue and runs them to completion.

Transient failures are re-enqueued with backoff until max_attempts is hit;
permanent or unexpected failures fail the job right away.
"""

from __future__ import annotations

import asyncio
import logging

from app.domain.errors import PermanentProcessingError, TransientProcessingError
from app.domain.models import Job
from app.ports.fetcher import DocumentFetcher
from app.ports.queue import JobQueue
from app.ports.repository import JobRepository
from app.processors.registry import get_processor
from app.services.retry import RetryPolicy, SleepFn

logger = logging.getLogger(__name__)


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

    async def process_one(self, job_id: str) -> None:
        """Process a single job id to a terminal or requeued state."""
        job = await self._repository.get(job_id)
        if job is None:
            logger.warning("job %s not found, skipping", job_id)
            return

        job.start()
        await self._repository.update(job)

        try:
            data = await self._fetcher.fetch(job.document_url)
            processor = get_processor(job.operation)
            result = await processor(data)
        except PermanentProcessingError as exc:
            job.fail(f"permanent: {exc}")
            await self._repository.update(job)
        except TransientProcessingError as exc:
            await self._handle_transient_failure(job, f"transient: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected error processing job %s", job.id)
            job.fail(f"unexpected: {exc}")
            await self._repository.update(job)
        else:
            job.succeed(result)
            await self._repository.update(job)

    async def _handle_transient_failure(self, job: Job, error: str) -> None:
        if job.can_retry:
            job.retry(error)
            await self._repository.update(job)
            await self._sleep(self._retry_policy.delay_for_attempt(job.attempts))
            await self._queue.enqueue(job.id)
        else:
            job.fail(error)
            await self._repository.update(job)
