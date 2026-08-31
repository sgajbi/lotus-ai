"""Exponential backoff with jitter and a total-attempt deadline (issue #153, S1).

Retryable provider attempts wait ``base * 2^(retry_index-1)`` seconds (capped
per delay) plus proportional jitter before the next attempt, and the whole
attempt sequence is bounded by a total deadline of
``timeout_seconds * attempts`` plus the maximum backoff sum - a retry can
never stretch the call beyond its declared budget: when the next delay would
cross the deadline, the attempt sequence stops and the failure is final.

The sleeper and jitter source are module seams (tests replace them for
determinism; production uses ``time.sleep`` and ``random.random``).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

BASE_DELAY_SECONDS = 0.25
MAX_DELAY_SECONDS = 4.0
JITTER_RATIO = 0.25

_sleep = time.sleep
_jitter_source = random.random


@dataclass(frozen=True)
class RetryBackoffPlan:
    timeout_seconds: float
    retry_limit: int

    def delay_before_retry(self, retry_index: int, *, jitter: float) -> float:
        """Delay before the retry with 1-based ``retry_index``; jitter in [0, 1)."""

        base = min(BASE_DELAY_SECONDS * (2 ** (retry_index - 1)), MAX_DELAY_SECONDS)
        return base * (1.0 + JITTER_RATIO * jitter)

    @property
    def total_deadline_seconds(self) -> float:
        attempts = self.retry_limit + 1
        max_backoff_sum = sum(
            min(BASE_DELAY_SECONDS * (2**index), MAX_DELAY_SECONDS)
            for index in range(self.retry_limit)
        ) * (1.0 + JITTER_RATIO)
        return self.timeout_seconds * attempts + max_backoff_sum


@dataclass(frozen=True)
class RetryDecision:
    permitted: bool
    delay_seconds: float


def plan_retry(
    plan: RetryBackoffPlan,
    *,
    retry_index: int,
    deadline_at: float,
    now: float | None = None,
) -> RetryDecision:
    """Decide whether the retry fits the deadline; the caller logs, then waits."""

    delay = plan.delay_before_retry(retry_index, jitter=_jitter_source())
    instant = time.perf_counter() if now is None else now
    if instant + delay > deadline_at:
        return RetryDecision(permitted=False, delay_seconds=delay)
    return RetryDecision(permitted=True, delay_seconds=delay)


def wait_for_retry(decision: RetryDecision) -> None:
    _sleep(decision.delay_seconds)
