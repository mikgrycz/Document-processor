"""End-to-end variants of the job lifecycle through the real API, worker,
and in-memory adapters: idempotent resubmission, retry-then-succeed, and
retry exhaustion.
"""

import time

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app


def _poll_until_terminal(client: TestClient, job_id: str, timeout: float = 6.0) -> dict:
    deadline = time.monotonic() + timeout
    body: dict = {}
    while time.monotonic() < deadline:
        body = client.get(f"/jobs/{job_id}").json()
        if body["status"] in {"succeeded", "failed"}:
            return body
        time.sleep(0.02)
    return body


def test_idempotent_resubmission_processes_the_job_only_once() -> None:
    with respx.mock:
        route = respx.get("https://example.com/doc.txt").mock(
            return_value=httpx.Response(200, content=b"hello world")
        )

        with TestClient(create_app()) as client:
            headers = {"Idempotency-Key": "same-key"}
            payload = {"document_url": "https://example.com/doc.txt", "operation": "word_count"}

            first = client.post("/jobs", json=payload, headers=headers)
            second = client.post("/jobs", json=payload, headers=headers)
            assert first.json()["id"] == second.json()["id"]

            final = _poll_until_terminal(client, first.json()["id"])

            assert final["status"] == "succeeded"
            assert route.call_count == 1


def test_fetcher_failing_twice_then_succeeding_is_retried_to_success() -> None:
    with respx.mock:
        route = respx.get("https://example.com/flaky.txt")
        route.side_effect = [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, content=b"one two three"),
        ]

        with TestClient(create_app()) as client:
            submit = client.post(
                "/jobs",
                json={"document_url": "https://example.com/flaky.txt", "operation": "word_count"},
            )

            final = _poll_until_terminal(client, submit.json()["id"])

            assert final["status"] == "succeeded"
            assert final["attempts"] == 3
            assert final["result"] == {"word_count": 3}
            assert route.call_count == 3


def test_fetcher_always_failing_exhausts_retries_and_fails() -> None:
    with respx.mock:
        route = respx.get("https://example.com/down.txt").mock(
            return_value=httpx.Response(503)
        )

        with TestClient(create_app()) as client:
            submit = client.post(
                "/jobs",
                json={"document_url": "https://example.com/down.txt", "operation": "sha256"},
            )

            final = _poll_until_terminal(client, submit.json()["id"])

            assert final["status"] == "failed"
            assert final["attempts"] == 4  # 1 initial attempt + 3 retries
            assert route.call_count == 4
