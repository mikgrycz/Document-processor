"""Unit tests for structured logging configuration."""

import json

import pytest

from app.observability.logging import configure_logging, get_logger


def test_logger_emits_json_with_the_bound_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logger = get_logger("test")

    logger.info("something_happened", job_id="abc123", attempt=2)

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["event"] == "something_happened"
    assert payload["job_id"] == "abc123"
    assert payload["attempt"] == 2
    assert payload["level"] == "info"
