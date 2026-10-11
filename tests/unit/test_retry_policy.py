"""Unit tests for the retry/backoff policy."""

from app.services.retry import RetryPolicy


def test_delay_is_bounded_by_exponential_backoff() -> None:
    policy = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=100.0)

    for attempt, expected_ceiling in [(1, 1.0), (2, 2.0), (3, 4.0)]:
        delay = policy.delay_for_attempt(attempt)
        assert 0.0 <= delay <= expected_ceiling


def test_delay_is_capped_at_max_delay() -> None:
    policy = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=3.0)

    delay = policy.delay_for_attempt(10)

    assert 0.0 <= delay <= 3.0
