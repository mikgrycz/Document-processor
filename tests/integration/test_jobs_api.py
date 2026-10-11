"""Integration test exercising the HTTP API, JobService, and in-memory
adapters together.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    # Fresh app per test: each app instance owns its own in-memory state.
    return TestClient(create_app())


def test_submit_job_returns_202_with_location_and_queued_status(client: TestClient) -> None:
    response = client.post(
        "/jobs", json={"document_url": "https://example.com/a.txt", "operation": "word_count"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["attempts"] == 0
    assert response.headers["location"] == f"/jobs/{body['id']}"


def test_get_job_returns_the_submitted_job(client: TestClient) -> None:
    submit_response = client.post(
        "/jobs", json={"document_url": "https://example.com/a.txt", "operation": "sha256"}
    )
    job_id = submit_response.json()["id"]

    get_response = client.get(f"/jobs/{job_id}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == job_id


def test_get_unknown_job_returns_404(client: TestClient) -> None:
    response = client.get("/jobs/does-not-exist")

    assert response.status_code == 404


def test_duplicate_submission_with_same_idempotency_key_returns_200_and_same_job(
    client: TestClient,
) -> None:
    payload = {"document_url": "https://example.com/a.txt", "operation": "word_count"}
    headers = {"Idempotency-Key": "key-1"}

    first = client.post("/jobs", json=payload, headers=headers)
    second = client.post("/jobs", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_same_idempotency_key_with_different_payload_returns_409(client: TestClient) -> None:
    headers = {"Idempotency-Key": "key-1"}
    client.post(
        "/jobs",
        json={"document_url": "https://example.com/a.txt", "operation": "word_count"},
        headers=headers,
    )

    response = client.post(
        "/jobs",
        json={"document_url": "https://example.com/b.txt", "operation": "word_count"},
        headers=headers,
    )

    assert response.status_code == 409


def test_invalid_url_scheme_is_rejected_with_422(client: TestClient) -> None:
    response = client.post(
        "/jobs", json={"document_url": "ftp://example.com/a.txt", "operation": "word_count"}
    )

    assert response.status_code == 422


def test_invalid_operation_is_rejected_with_422(client: TestClient) -> None:
    response = client.post(
        "/jobs", json={"document_url": "https://example.com/a.txt", "operation": "not_a_real_op"}
    )

    assert response.status_code == 422
