"""Retry backoff, jitter, and total-attempt deadline (issue #153, S1)."""

from email.message import Message
from io import BytesIO
from urllib import error

from pytest import MonkeyPatch, raises

from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.providers.openai_compatible_text_transport import post_openai_compatible_response
from app.services.provider_retry_backoff import (
    BASE_DELAY_SECONDS,
    JITTER_RATIO,
    MAX_DELAY_SECONDS,
    RetryBackoffPlan,
    plan_retry,
)


def test_delays_grow_exponentially_with_proportional_jitter_and_a_cap() -> None:
    plan = RetryBackoffPlan(timeout_seconds=4.0, retry_limit=6)

    without_jitter = [plan.delay_before_retry(index, jitter=0.0) for index in range(1, 7)]
    assert without_jitter == [0.25, 0.5, 1.0, 2.0, 4.0, 4.0]
    assert without_jitter[-1] == MAX_DELAY_SECONDS

    with_full_jitter = plan.delay_before_retry(1, jitter=1.0)
    assert with_full_jitter == BASE_DELAY_SECONDS * (1.0 + JITTER_RATIO)


def test_total_deadline_bounds_attempts_plus_maximum_backoff() -> None:
    plan = RetryBackoffPlan(timeout_seconds=4.0, retry_limit=2)
    # 3 attempts * 4s + (0.25 + 0.5) * 1.25 jitter headroom
    assert plan.total_deadline_seconds == 4.0 * 3 + 0.75 * 1.25


def test_plan_retry_refuses_when_the_delay_would_cross_the_deadline() -> None:
    plan = RetryBackoffPlan(timeout_seconds=1.0, retry_limit=1)

    inside = plan_retry(plan, retry_index=1, deadline_at=100.0, now=99.0)
    assert inside.permitted is True

    crossing = plan_retry(plan, retry_index=1, deadline_at=100.0, now=99.9)
    assert crossing.permitted is False
    assert crossing.delay_seconds > 0.0


def test_transport_backs_off_between_retries_and_succeeds(monkeypatch: MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "app.services.provider_retry_backoff._sleep", lambda delay: sleeps.append(delay)
    )
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)

    attempts = {"count": 0}

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id": "resp_backoff", "output_text": "OK"}'

    def _urlopen(request: object, timeout: float) -> _Response:
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise error.HTTPError(
                url="http://localhost/v1/responses",
                code=503,
                msg="unavailable",
                hdrs=Message(),
                fp=BytesIO(b"{}"),
            )
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    payload = post_openai_compatible_response(
        api_base="http://localhost:1234/v1",
        api_key=None,
        payload={"model": "m"},
        timeout_seconds=4.0,
        serving_provider_id="text.local",
        require_api_key=False,
        retry_limit=2,
    )

    assert payload["_lotus_retry_count"] == 2
    assert attempts["count"] == 3
    # Exponential, jitter-free (injected): first retry 0.25s, second 0.5s.
    assert sleeps == [0.25, 0.5]


def test_deadline_exhaustion_converts_a_retryable_failure_into_a_final_one(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)
    # Force every retry decision past the deadline.
    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.plan_retry",
        lambda plan, *, retry_index, deadline_at: __import__(
            "app.services.provider_retry_backoff", fromlist=["RetryDecision"]
        ).RetryDecision(permitted=False, delay_seconds=0.25),
    )

    attempts = {"count": 0}

    def _urlopen(request: object, timeout: float) -> object:
        attempts["count"] += 1
        raise TimeoutError()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    with raises(ProviderExecutionError) as exc_info:
        post_openai_compatible_response(
            api_base="http://localhost:1234/v1",
            api_key=None,
            payload={"model": "m"},
            timeout_seconds=1.0,
            serving_provider_id="text.local",
            require_api_key=False,
            retry_limit=5,
        )

    assert exc_info.value.category is ProviderFailureCategory.PROVIDER_TIMEOUT
    # The deadline stopped the sequence on the first attempt despite retry_limit=5.
    assert attempts["count"] == 1
