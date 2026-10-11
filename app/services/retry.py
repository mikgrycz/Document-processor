"""Retry/backoff policy used by the worker.

See Job.max_attempts for the "3 retries = 4 attempts total" assumption.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class RetryPolicy:
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 10.0

    def delay_for_attempt(self, attempt: int) -> float:
        """Exponential backoff with full jitter, for the 1-based attempt number."""
        exp_delay = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1)))
        return random.uniform(0, exp_delay)
