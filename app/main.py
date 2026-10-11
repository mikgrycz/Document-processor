"""Composition root: wires the FastAPI app.

This is intentionally minimal for now; routers, the worker lifespan, and
observability wiring are added in later commits as each piece is built.
"""

from fastapi import FastAPI

from app.adapters.memory_queue import InMemoryJobQueue
from app.adapters.memory_repository import InMemoryJobRepository
from app.api.routers import router as jobs_router
from app.services.job_service import JobService

__all__ = ["app"]


def create_app() -> FastAPI:
    application = FastAPI(title="Document Processor", version="0.1.0")

    repository = InMemoryJobRepository()
    queue = InMemoryJobQueue()
    application.state.job_service = JobService(repository=repository, queue=queue)
    application.state.queue = queue  # exposed for future readiness/metrics endpoints

    application.include_router(jobs_router)
    return application


app = create_app()
