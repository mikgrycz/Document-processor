"""Smoke test verifying the project scaffold and tooling are wired correctly."""

from fastapi.testclient import TestClient

from app.main import app


def test_app_can_be_instantiated() -> None:
    client = TestClient(app)
    assert client is not None
