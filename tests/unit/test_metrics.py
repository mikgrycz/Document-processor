"""Unit tests for Prometheus metrics wiring."""

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.adapters.memory_queue import InMemoryJobQueue
from app.adapters.memory_repository import InMemoryJobRepository
from app.domain.errors import TransientProcessingError
from app.domain.models import Job, Operation
from app.main import create_app
from app.services.worker import Worker


class _AlwaysTransientFetcher:
    async def fetch(self, url: str) -> bytes:
        raise TransientProcessingError("boom")


async def _noop_sleep(seconds: float) -> None:
    return None


def test_metrics_endpoint_exposes_submitted_jobs_and_queue_depth() -> None:
    with TestClient(create_app()) as client:
        client.post(
            "/jobs",
            json={"document_url": "https://example.com/a.txt", "operation": "word_count"},
        )

        response = client.get("/metrics")

        assert response.status_code == 200
        body = response.text
        assert 'jobs_submitted_total{operation="word_count"}' in body
        assert "jobs_queue_depth" in body


async def test_worker_retry_increments_retries_counter() -> None:
    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    job = Job(document_url="https://example.com/a.txt", operation=Operation.WORD_COUNT)
    await repository.add(job)
    await queue.enqueue(job.id)

    before = REGISTRY.get_sample_value("job_retries_total") or 0.0

    worker = Worker(
        repository=repository,
        queue=queue,
        fetcher=_AlwaysTransientFetcher(),
        sleep=_noop_sleep,
    )
    await worker.process_one(await queue.dequeue())

    after = REGISTRY.get_sample_value("job_retries_total")
    assert after == before + 1
