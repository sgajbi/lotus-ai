"""max_latency_ms is one governed end-to-end execution budget (issue #244).

The requirement was previously applied as an individual provider-attempt
timeout while its evidence said ENFORCED: retries, backoff and ordered
fallback each started a fresh clock, so total latency could exceed the
caller's stated maximum. These tests drive the real transport and gateway
under a fake monotonic clock and a fake sleeper, and pin the invariant for
every path: **total governed elapsed time never exceeds the requirement**,
beyond documented clock granularity.

The clock advances only when the fakes say so: each provider attempt costs
what the fake upstream decides, each backoff sleep costs its full delay, and
nothing else moves time - so any budget overrun is the runtime's fault, not
the harness's.
"""

from __future__ import annotations

from email.message import Message
from io import BytesIO
from json import dumps
from urllib import error

import pytest

from app.config import settings
from app.contracts.capability_requirements import CapabilityRequirements
from app.contracts.providers import (
    ProviderExecutionRequest,
    ProviderFailureCategory,
)
from app.services.provider_gateway import (
    ProviderGatewayUnavailableError,
    execute_text_generation,
)
from tests.unit.test_ordered_fallback_routing import (
    ALTERNATE,
    PRIMARY,
    _assess_structured_output,
    _ordered_fallback_settings,
    _request,
)

BUDGET_MS = 2_000


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _FakeUpstream:
    """Scripted provider attempts: each entry is (seconds_spent, outcome).

    outcome "ok" returns a valid payload; "http_503" raises a retryable
    upstream error; "timeout" raises TimeoutError. Attempts that exceed the
    scripted duration never happen - the fake IS the elapsed time.
    """

    def __init__(self, clock: _FakeClock, script: list[tuple[float, str]]) -> None:
        self.clock = clock
        self.script = list(script)
        self.attempt_timeouts: list[float] = []

    def __call__(self, request: object, timeout: float) -> object:
        self.attempt_timeouts.append(timeout)
        seconds, outcome = self.script.pop(0)
        # An attempt can never take longer than the timeout it was given.
        self.clock.advance(min(seconds, timeout))
        if outcome == "ok":
            payload = {
                "id": "resp_budget",
                "model": "gpt-5.4",
                "output_text": "Grounded explanation without figures.",
                "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
            }

            class _Response:
                def __enter__(self) -> "_Response":
                    return self

                def __exit__(self, *args: object) -> None:
                    return None

                def read(self) -> bytes:
                    return dumps(payload).encode("utf-8")

            return _Response()
        if outcome == "http_503":
            raise error.HTTPError(
                url="https://api.test/responses",
                code=503,
                msg="Service Unavailable",
                hdrs=Message(),
                fp=BytesIO(b"{}"),
            )
        raise TimeoutError("scripted timeout")


@pytest.fixture()
def harness(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr("app.services.provider_gateway._monotonic", clock)
    monkeypatch.setattr("app.providers.openai_compatible_text_transport._monotonic", clock)
    # plan_retry consults the real clock unless given one; route it here too.
    monkeypatch.setattr(
        "app.services.provider_retry_backoff.time",
        type("T", (), {"perf_counter": staticmethod(clock), "sleep": None}),
    )
    # Backoff sleeps advance the fake clock instead of blocking.
    monkeypatch.setattr(
        "app.services.provider_retry_backoff._sleep", lambda seconds: clock.advance(seconds)
    )
    # Deterministic jitter.
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)
    return clock


def _install_upstream(
    monkeypatch: pytest.MonkeyPatch, clock: _FakeClock, script: list[tuple[float, str]]
) -> _FakeUpstream:
    upstream = _FakeUpstream(clock, script)
    monkeypatch.setattr("urllib.request.urlopen", upstream)
    return upstream


def _budget_request(retry_limit: int = 0) -> ProviderExecutionRequest:
    return _request(
        timeout_ms=10_000,
        retry_limit=retry_limit,
        requirements=CapabilityRequirements(max_latency_ms=BUDGET_MS),
    )


def _elapsed_ms(clock: _FakeClock, started: float) -> float:
    return (clock.now - started) * 1000.0


def _settings_with_assessed_candidates(retry_limit: int = 0) -> None:
    _ordered_fallback_settings()
    settings.provider_retry_limit = retry_limit
    _assess_structured_output(PRIMARY, "gpt-5.4", True)
    _assess_structured_output(ALTERNATE, "claude-sonnet-5", True)


def test_single_successful_attempt_stays_within_budget(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings_with_assessed_candidates()
    _install_upstream(monkeypatch, harness, [(0.5, "ok")])
    started = harness.now

    response = execute_text_generation(_budget_request())

    assert response.provider_id == PRIMARY
    assert _elapsed_ms(harness, started) <= BUDGET_MS


def test_failed_attempt_then_retry_stays_within_budget(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings_with_assessed_candidates()
    upstream = _install_upstream(monkeypatch, harness, [(0.8, "http_503"), (0.5, "ok")])
    started = harness.now

    response = execute_text_generation(_budget_request(retry_limit=1))

    assert response.provider_id == PRIMARY
    assert len(upstream.attempt_timeouts) == 2
    assert _elapsed_ms(harness, started) <= BUDGET_MS
    # The second attempt received only the remaining budget, not a fresh one.
    assert upstream.attempt_timeouts[1] < upstream.attempt_timeouts[0]


def test_retry_backoff_sleep_counts_against_the_budget(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings_with_assessed_candidates()
    upstream = _install_upstream(
        monkeypatch, harness, [(0.6, "http_503"), (0.6, "http_503"), (0.4, "ok")]
    )
    started = harness.now

    response = execute_text_generation(_budget_request(retry_limit=2))

    assert response.provider_id == PRIMARY
    assert len(upstream.attempt_timeouts) == 3
    assert _elapsed_ms(harness, started) <= BUDGET_MS


def test_primary_failure_then_alternate_shares_one_budget(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The budget is never reset when moving from primary to alternate: the
    alternate's attempt timeout is what the primary left behind."""

    _settings_with_assessed_candidates()
    upstream = _install_upstream(monkeypatch, harness, [(1.2, "timeout"), (0.5, "ok")])
    started = harness.now

    response = execute_text_generation(_budget_request())

    assert response.provider_id == ALTERNATE
    assert _elapsed_ms(harness, started) <= BUDGET_MS
    assert len(upstream.attempt_timeouts) == 2
    assert upstream.attempt_timeouts[1] <= (BUDGET_MS / 1000.0) - 1.2 + 0.001


def test_multiple_retries_plus_fallback_stay_within_budget(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings_with_assessed_candidates()
    upstream = _install_upstream(
        monkeypatch,
        harness,
        [(0.5, "http_503"), (0.5, "timeout"), (0.4, "http_503"), (0.3, "ok")],
    )
    started = harness.now

    response = execute_text_generation(_budget_request(retry_limit=1))

    assert response.provider_id == ALTERNATE
    assert len(upstream.attempt_timeouts) == 4
    assert _elapsed_ms(harness, started) <= BUDGET_MS


def test_deadline_exhaustion_refuses_the_alternate_distinctly(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the primary consumes the whole budget, the alternate never starts,
    and the rejection says the DEADLINE ran out - not that a provider timed
    out or degraded. Distinguishability is the point: the provider did
    nothing wrong."""

    _settings_with_assessed_candidates()
    upstream = _install_upstream(monkeypatch, harness, [(BUDGET_MS / 1000.0, "timeout")])
    started = harness.now

    with pytest.raises(ProviderGatewayUnavailableError) as exc_info:
        execute_text_generation(_budget_request())

    decision = exc_info.value.routing_decision
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.PROVIDER_TIMEOUT
    assert decision.candidates[1].rejection_reason is (
        ProviderFailureCategory.REQUEST_DEADLINE_EXHAUSTED
    )
    # Only the primary ever attempted; the alternate was refused pre-attempt.
    assert len(upstream.attempt_timeouts) == 1
    assert _elapsed_ms(harness, started) <= BUDGET_MS + 1


def test_exhaustion_mid_retry_is_distinct_from_provider_timeout(
    harness: _FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry that no remaining budget can support refuses as deadline
    exhaustion at the transport, never as another provider condition."""

    _settings_with_assessed_candidates()
    _install_upstream(
        monkeypatch,
        harness,
        [(1.9, "http_503"), (1.9, "http_503"), (1.9, "http_503")],
    )

    with pytest.raises(ProviderGatewayUnavailableError) as exc_info:
        execute_text_generation(_budget_request(retry_limit=2))

    reasons = {c.rejection_reason for c in exc_info.value.routing_decision.candidates}
    assert ProviderFailureCategory.REQUEST_DEADLINE_EXHAUSTED in reasons


def test_no_budget_declared_means_no_deadline_machinery() -> None:
    """Absent max_latency_ms, nothing changes: no deadline is stamped and the
    request routes exactly as before the budget existed."""

    request = _request(timeout_ms=4_000)
    assert request.execution_deadline_at is None
