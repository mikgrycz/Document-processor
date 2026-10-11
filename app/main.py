"""Composition root: wires the FastAPI app.

This is intentionally minimal for now; routers, the worker lifespan, and
observability wiring are added in later commits as each piece is built.
"""

from fastapi import FastAPI

__all__ = ["app"]


def create_app() -> FastAPI:
    application = FastAPI(title="Document Processor", version="0.1.0")
    return application


app = create_app()
