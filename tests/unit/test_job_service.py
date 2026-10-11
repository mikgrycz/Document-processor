"""Unit tests for JobService: submission, idempotency, and lookup."""

import asyncio

import pytest

from app.adapters.memory_queue import InMemoryJobQueue
from app.adapters.memory_repository import InMemoryJobRepository
from app.domain.models import Operation
from app.services.job_service import IdempotencyConflictError, JobService


def make_service() -> JobService:
    return JobService(repository=InMemoryJobRepository(), queue=InMemoryJobQueue())


async def test_submit_creates_a_queued_job_and_enqueues_it() -> None:
    service = make_service()

    job, created = await service.submit("https://example.com/a.txt", Operation.WORD_COUNT)

    assert created is True
    assert job.status.value == "queued"
    assert await service.get(job.id) is job


async def test_submit_without_idempotency_key_always_creates_new_job() -> None:
    service = make_service()

    job1, _ = await service.submit("https://example.com/a.txt", Operation.WORD_COUNT)
    job2, _ = await service.submit("https://example.com/a.txt", Operation.WORD_COUNT)

    assert job1.id != job2.id


async def test_submit_with_same_idempotency_key_and_payload_returns_existing_job() -> None:
    service = make_service()

    job1, created1 = await service.submit(
        "https://example.com/a.txt", Operation.WORD_COUNT, idempotency_key="key-1"
    )
    job2, created2 = await service.submit(
        "https://example.com/a.txt", Operation.WORD_COUNT, idempotency_key="key-1"
    )

    assert created1 is True
    assert created2 is False
    assert job1.id == job2.id


async def test_submit_with_same_key_and_different_payload_raises_conflict() -> None:
    service = make_service()
    await service.submit(
        "https://example.com/a.txt", Operation.WORD_COUNT, idempotency_key="key-1"
    )

    with pytest.raises(IdempotencyConflictError):
        await service.submit(
            "https://example.com/b.txt", Operation.WORD_COUNT, idempotency_key="key-1"
        )


async def test_concurrent_submissions_with_same_key_create_exactly_one_job() -> None:
    service = make_service()

    results = await asyncio.gather(
        *[
            service.submit(
                "https://example.com/a.txt", Operation.WORD_COUNT, idempotency_key="key-1"
            )
            for _ in range(20)
        ]
    )

    job_ids = {job.id for job, _ in results}
    created_count = sum(1 for _, created in results if created)

    assert len(job_ids) == 1
    assert created_count == 1


async def test_get_unknown_job_returns_none() -> None:
    service = make_service()

    assert await service.get("missing") is None
