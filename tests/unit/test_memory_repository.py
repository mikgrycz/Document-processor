"""Unit tests for the in-memory JobRepository adapter."""

from app.adapters.memory_repository import InMemoryJobRepository
from app.domain.models import Job, Operation


def make_job(**overrides: object) -> Job:
    defaults: dict[str, object] = {
        "document_url": "https://example.com/doc.txt",
        "operation": Operation.WORD_COUNT,
    }
    defaults.update(overrides)
    return Job(**defaults)  # type: ignore[arg-type]


async def test_add_and_get_round_trip() -> None:
    repo = InMemoryJobRepository()
    job = make_job()

    await repo.add(job)

    assert await repo.get(job.id) is job


async def test_get_unknown_id_returns_none() -> None:
    repo = InMemoryJobRepository()

    assert await repo.get("missing") is None


async def test_get_by_idempotency_key_finds_matching_job() -> None:
    repo = InMemoryJobRepository()
    job = make_job(idempotency_key="key-1")
    await repo.add(job)

    found = await repo.get_by_idempotency_key("key-1")

    assert found is job


async def test_get_by_idempotency_key_returns_none_when_absent() -> None:
    repo = InMemoryJobRepository()

    assert await repo.get_by_idempotency_key("unused-key") is None


async def test_update_persists_mutated_job() -> None:
    repo = InMemoryJobRepository()
    job = make_job()
    await repo.add(job)

    job.start()
    await repo.update(job)

    stored = await repo.get(job.id)
    assert stored is not None
    assert stored.status == job.status
