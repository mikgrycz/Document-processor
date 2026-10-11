"""Core domain model: the Job entity and its state machine.

This module has no dependency on FastAPI, storage libraries, or any other
infrastructure concern — it is pure business logic and is tested in
isolation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Operation(str, Enum):
    """Supported document-processing operations."""

    WORD_COUNT = "word_count"
    SHA256 = "sha256"
    METADATA = "metadata"


class InvalidTransitionError(Exception):
    """Raised when a requested state transition violates the state machine."""

    def __init__(self, current: JobStatus, target: JobStatus) -> None:
        super().__init__(f"cannot transition job from '{current.value}' to '{target.value}'")
        self.current = current
        self.target = target


# Valid next states for each status. SUCCEEDED and FAILED are terminal.
_ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING}),
    JobStatus.RUNNING: frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.QUEUED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Job:
    """A document-processing job and its lifecycle.

    Assumption: "retry up to three times" is interpreted as one initial
    attempt plus three retries, i.e. ``max_attempts`` total attempts
    (default 4). See README for the full list of documented assumptions.
    """

    document_url: str
    operation: Operation
    idempotency_key: str | None = None
    max_attempts: int = 4
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    result: Any | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def _transition(self, target: JobStatus) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransitionError(self.status, target)
        self.status = target
        self.updated_at = _utcnow()

    def start(self) -> None:
        """Claim the job for processing: queued -> running."""
        self._transition(JobStatus.RUNNING)
        self.attempts += 1

    def succeed(self, result: Any) -> None:
        """Record a successful outcome: running -> succeeded."""
        self._transition(JobStatus.SUCCEEDED)
        self.result = result
        self.error = None

    def retry(self, error: str) -> None:
        """Return a job to the queue after a transient failure: running -> queued."""
        self.error = error
        self._transition(JobStatus.QUEUED)

    def fail(self, error: str) -> None:
        """Mark the job as permanently failed: running -> failed."""
        self.error = error
        self._transition(JobStatus.FAILED)

    @property
    def can_retry(self) -> bool:
        """Whether another attempt is allowed under ``max_attempts``."""
        return self.attempts < self.max_attempts
