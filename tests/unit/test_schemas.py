"""Unit tests for the jobs API request schema validation."""

import pytest
from pydantic import ValidationError

from app.api.schemas import JobSubmitRequest


def test_accepts_http_and_https_urls() -> None:
    JobSubmitRequest(document_url="http://example.com/a.txt", operation="word_count")
    JobSubmitRequest(document_url="https://example.com/a.txt", operation="sha256")


@pytest.mark.parametrize(
    "url", ["ftp://example.com/a.txt", "file:///etc/passwd", "not-a-url", ""]
)
def test_rejects_non_http_schemes(url: str) -> None:
    with pytest.raises(ValidationError):
        JobSubmitRequest(document_url=url, operation="word_count")


def test_rejects_unknown_operation() -> None:
    with pytest.raises(ValidationError):
        JobSubmitRequest(document_url="https://example.com/a.txt", operation="not_a_real_op")
