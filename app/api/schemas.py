"""Pydantic request/response models for the jobs API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import JobStatus, Operation

_ALLOWED_SCHEMES = {"http", "https"}


class JobSubmitRequest(BaseModel):
    document_url: str = Field(..., description="HTTP(S) URL of the document to process")
    operation: Operation

    @field_validator("document_url")
    @classmethod
    def validate_scheme(cls, value: str) -> str:
        scheme = value.split("://", 1)[0].lower() if "://" in value else ""
        if scheme not in _ALLOWED_SCHEMES:
            raise ValueError("document_url must use http:// or https://")
        return value


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: JobStatus
    operation: Operation
    document_url: str
    attempts: int
    result: Any | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
