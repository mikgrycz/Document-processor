"""Unit tests for Worker.resync(): recovering queued/running jobs on startup."""

from app.adapters.memory_queue import InMemoryJobQueue
from app.adapters.memory_repository import InMemoryJobRepository
from app.domain.models import Job, Operation
from app.services.worker import Worker


class _UnusedFetcher:
    async def fetch(self, url: str) -> bytes:
        raise AssertionError("resync should not fetch anything")


def make_worker(repository: InMemoryJobRepository, queue: InMemoryJobQueue) -> Worker:
    return Worker(repository=repository, queue=queue, fetcher=_UnusedFetcher())


async def test_resync_requeues_queued_and_running_jobs() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    queued_job = Job(document_url="https://example.com/a.txt", operation=Operation.WORD_COUNT)
    running_job = Job(document_url="https://example.com/b.txt", operation=Operation.WORD_COUNT)
    running_job.start()
    await repository.add(queued_job)
    await repository.add(running_job)

    await make_worker(repository, queue).resync()

    assert queue.depth() == 2
    stored_running = await repository.get(running_job.id)
    assert stored_running is not None
    assert stored_running.status.value == "queued"


async def test_resync_ignores_terminal_jobs() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    done_job = Job(document_url="https://example.com/c.txt", operation=Operation.WORD_COUNT)
    done_job.start()
    done_job.succeed({"ok": True})
    await repository.add(done_job)

    await make_worker(repository, queue).resync()

    assert queue.depth() == 0
