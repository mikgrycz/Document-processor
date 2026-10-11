"""Unit tests for liveness and readiness endpoints."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_liveness_is_always_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200


def test_readiness_is_503_before_the_app_lifespan_starts() -> None:
    # Without entering the TestClient as a context manager, lifespan
    # startup never runs, so the worker never sets the ready event.
    client = TestClient(create_app())

    response = client.get("/readyz")

    assert response.status_code == 503


def test_readiness_is_200_once_the_app_lifespan_has_started() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/readyz")

        assert response.status_code == 200
