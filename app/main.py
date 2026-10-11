"""Composition root: wires the FastAPI app, adapters, and worker lifespan."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.http_fetcher import HttpDocumentFetcher
from app.adapters.memory_queue import InMemoryJobQueue
from app.adapters.memory_repository import InMemoryJobRepository
from app.api.health import router as health_router
from app.api.routers import router as jobs_router
from app.config import settings
from app.services.job_service import JobService
from app.services.worker import Worker

__all__ = ["app"]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    worker = Worker(
        repository=application.state.repository,
        queue=application.state.queue,
        fetcher=HttpDocumentFetcher(),
    )
    await worker.resync()

    tasks = [
        asyncio.create_task(worker.run_forever()) for _ in range(settings.worker_concurrency)
    ]
    application.state.ready_event.set()

    try:
        yield
    finally:
        application.state.ready_event.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    application = FastAPI(title="Document Processor", version="0.1.0", lifespan=lifespan)

    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    application.state.repository = repository
    application.state.queue = queue
    application.state.job_service = JobService(repository=repository, queue=queue)
    application.state.ready_event = asyncio.Event()

    application.include_router(jobs_router)
    application.include_router(health_router)
    return application


app = create_app()
