"""Integration test proving the full stack (API + service + worker +
adapters) processes a submitted job once the app's lifespan is running.
"""

import time

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import create_app


def test_submitted_job_is_processed_by_the_background_worker() -> None:
    with respx.mock:
        respx.get("https://example.com/doc.txt").mock(
            return_value=httpx.Response(200, content=b"hello world")
        )

        with TestClient(create_app()) as client:
            submit = client.post(
                "/jobs",
                json={"document_url": "https://example.com/doc.txt", "operation": "word_count"},
            )
            job_id = submit.json()["id"]

            final = None
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                final = client.get(f"/jobs/{job_id}").json()
                if final["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.01)

            assert final is not None
            assert final["status"] == "succeeded"
            assert final["result"] == {"word_count": 2}
