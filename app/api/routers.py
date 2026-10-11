"""HTTP routes for job submission and status lookup.

Thin by design: validation lives in the Pydantic schemas, orchestration
lives in JobService. This layer only translates HTTP <-> domain calls.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.api.schemas import JobResponse, JobSubmitRequest
from app.services.job_service import IdempotencyConflictError, JobService

router = APIRouter(tags=["jobs"])


def get_job_service(request: Request) -> JobService:
    service: JobService = request.app.state.job_service
    return service


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    payload: JobSubmitRequest,
    response: Response,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobResponse:
    """Accept a document for processing.

    Returns 202 with a Location header for a newly created job. If the
    Idempotency-Key matches a prior request with the same payload, the
    existing job is returned instead with 200 OK (no new job is created).
    """
    service = get_job_service(request)
    try:
        job, created = await service.submit(
            document_url=payload.document_url,
            operation=payload.operation,
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    response.headers["Location"] = f"/jobs/{job.id}"
    if not created:
        response.status_code = status.HTTP_200_OK
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, request: Request) -> JobResponse:
    service = get_job_service(request)
    job = await service.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return JobResponse.model_validate(job)
