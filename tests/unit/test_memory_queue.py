"""Unit tests for the in-memory JobQueue adapter."""

from app.adapters.memory_queue import InMemoryJobQueue


async def test_depth_reflects_pending_items() -> None:
    queue = InMemoryJobQueue()
    assert queue.depth() == 0

    await queue.enqueue("job-1")
    await queue.enqueue("job-2")

    assert queue.depth() == 2


async def test_dequeue_returns_items_in_fifo_order() -> None:
    queue = InMemoryJobQueue()
    await queue.enqueue("job-1")
    await queue.enqueue("job-2")

    assert await queue.dequeue() == "job-1"
    assert await queue.dequeue() == "job-2"
    assert queue.depth() == 0
