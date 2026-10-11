"""/metrics endpoint exposing Prometheus metrics."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.observability.metrics import jobs_queue_depth

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    jobs_queue_depth.set(request.app.state.queue.depth())
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
