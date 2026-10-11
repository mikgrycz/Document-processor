"""Unit tests for the Worker: happy path, retries, and permanent failures."""

from __future__ import annotations

from app.adapters.memory_queue import InMemoryJobQueue
from app.adapters.memory_repository import InMemoryJobRepository
from app.domain.errors import PermanentProcessingError, TransientProcessingError
from app.domain.models import Job, Operation
from app.services.retry import RetryPolicy
from app.services.worker import Worker


class FakeFetcher:
    """Returns queued responses/exceptions in order, one per call."""

    def __init__(self, behaviors: list[object]) -> None:
        self._behaviors = list(behaviors)
        self.calls = 0

    async def fetch(self, url: str) -> bytes:
        self.calls += 1
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        assert isinstance(behavior, bytes)
        return behavior


async def _noop_sleep(seconds: float) -> None:
    return None


def make_worker(fetcher: FakeFetcher, repository, queue) -> Worker:
    return Worker(
        repository=repository,
        queue=queue,
        fetcher=fetcher,
        retry_policy=RetryPolicy(base_delay_seconds=0, max_delay_seconds=0),
        sleep=_noop_sleep,
    )


async def _drain(worker: Worker, queue: InMemoryJobQueue) -> None:
    while queue.depth() > 0:
        job_id = await queue.dequeue()
        await worker.process_one(job_id)


async def test_successful_job_is_marked_succeeded_with_result() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    job = Job(document_url="https://example.com/a.txt", operation=Operation.WORD_COUNT)
    await repository.add(job)
    await queue.enqueue(job.id)

    fetcher = FakeFetcher([b"two words"])
    worker = make_worker(fetcher, repository, queue)
    await _drain(worker, queue)

    stored = await repository.get(job.id)
    assert stored.status.value == "succeeded"
    assert stored.result == {"word_count": 2}
    assert stored.attempts == 1


async def test_transient_failure_is_retried_until_it_succeeds() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    job = Job(document_url="https://example.com/a.txt", operation=Operation.SHA256)
    await repository.add(job)
    await queue.enqueue(job.id)

    fetcher = FakeFetcher(
        [TransientProcessingError("timeout"), TransientProcessingError("timeout"), b"data"]
    )
    worker = make_worker(fetcher, repository, queue)
    await _drain(worker, queue)

    stored = await repository.get(job.id)
    assert stored.status.value == "succeeded"
    assert stored.attempts == 3
    assert fetcher.calls == 3


async def test_transient_failure_exhausts_retries_and_fails() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    job = Job(
        document_url="https://example.com/a.txt", operation=Operation.SHA256, max_attempts=2
    )
    await repository.add(job)
    await queue.enqueue(job.id)

    fetcher = FakeFetcher([TransientProcessingError("timeout")] * 2)
    worker = make_worker(fetcher, repository, queue)
    await _drain(worker, queue)

    stored = await repository.get(job.id)
    assert stored.status.value == "failed"
    assert stored.attempts == 2
    assert "transient" in stored.error
    assert fetcher.calls == 2


async def test_permanent_failure_fails_immediately_without_retry() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    job = Job(document_url="https://example.com/missing.txt", operation=Operation.METADATA)
    await repository.add(job)
    await queue.enqueue(job.id)

    fetcher = FakeFetcher([PermanentProcessingError("404 Not Found")])
    worker = make_worker(fetcher, repository, queue)
    await _drain(worker, queue)

    stored = await repository.get(job.id)
    assert stored.status.value == "failed"
    assert stored.attempts == 1
    assert "permanent" in stored.error
    assert fetcher.calls == 1


async def test_unexpected_exception_fails_job_instead_of_hanging_in_running() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    job = Job(document_url="https://example.com/a.txt", operation=Operation.WORD_COUNT)
    await repository.add(job)
    await queue.enqueue(job.id)

    fetcher = FakeFetcher([RuntimeError("boom")])
    worker = make_worker(fetcher, repository, queue)
    await _drain(worker, queue)

    stored = await repository.get(job.id)
    assert stored.status.value == "failed"
    assert "unexpected" in stored.error


async def test_missing_job_is_skipped_without_error() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    fetcher = FakeFetcher([])
    worker = make_worker(fetcher, repository, queue)

    await worker.process_one("does-not-exist")

    assert fetcher.calls == 0
