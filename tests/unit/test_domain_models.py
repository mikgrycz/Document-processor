"""Unit tests for the Job entity and its state machine."""

import pytest

from app.domain.models import InvalidTransitionError, Job, JobStatus, Operation


def make_job(**overrides: object) -> Job:
    defaults: dict[str, object] = {
        "document_url": "https://example.com/doc.txt",
        "operation": Operation.WORD_COUNT,
    }
    defaults.update(overrides)
    return Job(**defaults)  # type: ignore[arg-type]


def test_new_job_starts_queued_with_no_attempts() -> None:
    job = make_job()

    assert job.status == JobStatus.QUEUED
    assert job.attempts == 0
    assert job.result is None
    assert job.error is None


def test_start_transitions_to_running_and_counts_attempt() -> None:
    job = make_job()

    job.start()

    assert job.status == JobStatus.RUNNING
    assert job.attempts == 1


def test_succeed_records_result_and_clears_error() -> None:
    job = make_job()
    job.start()
    job.error = "stale error from a previous attempt"

    job.succeed(result={"words": 42})

    assert job.status == JobStatus.SUCCEEDED
    assert job.result == {"words": 42}
    assert job.error is None


def test_fail_records_error_and_is_terminal() -> None:
    job = make_job()
    job.start()

    job.fail("permanent: 404 Not Found")

    assert job.status == JobStatus.FAILED
    assert job.error == "permanent: 404 Not Found"


def test_retry_returns_job_to_queue_and_keeps_attempt_count() -> None:
    job = make_job()
    job.start()

    job.retry("transient: connection timed out")

    assert job.status == JobStatus.QUEUED
    assert job.error == "transient: connection timed out"
    assert job.attempts == 1  # the failed attempt still counts

    job.start()
    assert job.attempts == 2


def _leave_queued(job: Job) -> None:
    pass


def _move_to_succeeded(job: Job) -> None:
    job.start()
    job.succeed(None)


def _move_to_failed(job: Job) -> None:
    job.start()
    job.fail("x")


@pytest.mark.parametrize(
    ("setup", "target"),
    [
        (_leave_queued, "succeed"),  # queued -> succeeded is illegal
        (_leave_queued, "fail"),  # queued -> failed is illegal
        (_move_to_succeeded, "start"),  # succeeded -> running is illegal
        (_move_to_failed, "retry"),  # failed -> queued is illegal
    ],
)
def test_illegal_transitions_are_rejected(setup, target: str) -> None:
    job = make_job()
    setup(job)

    method = getattr(job, target)
    with pytest.raises(InvalidTransitionError):
        if target == "succeed":
            method(None)
        elif target in {"fail", "retry"}:
            method("error")
        else:
            method()


def test_can_retry_respects_max_attempts() -> None:
    job = make_job(max_attempts=2)

    assert job.can_retry is True
    job.start()
    assert job.can_retry is True
    job.retry("transient")
    job.start()
    assert job.can_retry is False
