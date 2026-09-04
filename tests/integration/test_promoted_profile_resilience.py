"""The #153 evaluation condition, end to end under promoted protections.

A fake provider that fails twice then succeeds completes after two
backed-off retries within the deadline; an always-failing provider opens
the breaker after the threshold and subsequent calls are rejected fast at
preflight without reaching the transport; the enforcement counters are
visible from a second repository instance, as a second replica would see
them.
"""

from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib import error

from fastapi import HTTPException
from pytest import MonkeyPatch, raises

from app.config import settings
from app.contracts.providers import ProviderQuotaScope
from app.contracts.tasks import OutputLabel
from app.repositories.sqlalchemy_provider_operations_repository import (
    SqlAlchemyProviderOperationsRepository,
)
from app.services.task_executor import execute_task
from tests.support.migration_runner import upgrade_database_to_head
from tests.unit.test_task_executor import _request


def _promoted_live_settings(tmp_path: Path) -> str:
    # The promoted protection set (S2 derives these from the profile; the
    # derivation itself is unit-tested - here the protections run live)
    # plus the operator-supplied limits promoted demands.
    settings.runtime_profile = "promoted"
    settings.provider_retry_limit = 2
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 3
    settings.live_text_circuit_open_seconds = 60
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=100"
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 100.0
    settings.live_text_input_cost_per_1k_tokens = 0.0
    settings.live_text_output_cost_per_1k_tokens = 0.0
    settings.provider_operations_store_mode = "sqlalchemy"
    database_url = f"sqlite:///{tmp_path / 'promoted-resilience.db'}"
    settings.database_url = database_url
    upgrade_database_to_head(database_url)

    settings.provider_mode = "local_openai_compatible"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.local"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_allowed_task_ids = "explain.v1"
    return database_url


def _fake_probe(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
        lambda: type(
            "ProbeStatus",
            (),
            {"endpoint_reachable": True, "model_available": True, "blocking_reason": None},
        )(),
    )


class _SuccessResponse:
    def __enter__(self) -> "_SuccessResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return (
            b'{"id": "resp_resilient", "model": "qwen3:8b",'
            b' "output_text": "Recovered live response.",'
            b' "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}'
        )


def _http_503() -> error.HTTPError:
    return error.HTTPError(
        url="http://ollama:11434/v1/responses",
        code=503,
        msg="unavailable",
        hdrs=Message(),
        fp=BytesIO(b"{}"),
    )


def test_fails_twice_then_succeeds_within_backed_off_deadline(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_url = _promoted_live_settings(tmp_path)
    _fake_probe(monkeypatch)

    sleeps: list[float] = []
    monkeypatch.setattr(
        "app.services.provider_retry_backoff._sleep", lambda delay: sleeps.append(delay)
    )
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)

    attempts = {"count": 0}

    def _urlopen(request: object, timeout: float) -> object:
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise _http_503()
        return _SuccessResponse()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == "COMPLETED"
    assert response.result.message == "Recovered live response."
    assert attempts["count"] == 3
    assert sleeps == [0.25, 0.5]
    assert response.result.structured_output["retry_count"] == 2

    # The quota and budget counters are durable and visible from a second
    # repository instance - what a second replica would read.
    second_replica = SqlAlchemyProviderOperationsRepository(database_url)
    quota = second_replica.get_quota_state(scope=ProviderQuotaScope.TASK, scope_key="explain.v1")
    assert quota is not None
    assert quota.request_count == 1
    budget = second_replica.get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == 0.0  # zero-rate card: recorded spend, zero cost


def test_always_failing_provider_opens_the_breaker_and_fast_rejects(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    database_url = _promoted_live_settings(tmp_path)
    _fake_probe(monkeypatch)
    monkeypatch.setattr("app.services.provider_retry_backoff._sleep", lambda delay: None)
    monkeypatch.setattr("app.services.provider_retry_backoff._jitter_source", lambda: 0.0)

    attempts = {"count": 0}

    def _urlopen(request: object, timeout: float) -> object:
        attempts["count"] += 1
        raise _http_503()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    failures = 0
    for _ in range(3):
        with raises(HTTPException):
            execute_task(_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY))
        failures += 1
    assert failures == 3
    transport_attempts_when_breaker_opened = attempts["count"]

    # The breaker is open: the next call is rejected at preflight without
    # reaching the transport at all.
    with raises(HTTPException) as exc_info:
        execute_task(_request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY))
    assert "CIRCUIT_OPEN" in str(exc_info.value.detail)
    assert attempts["count"] == transport_attempts_when_breaker_opened

    # The enforcement state is durable and visible from a second repository
    # instance - what a second replica would read.
    second_replica = SqlAlchemyProviderOperationsRepository(database_url)
    # Failure bookkeeping is keyed per CANONICAL candidate identity
    # (issues #304, #314).
    from app.contracts.model_catalogue import derive_candidate_identity_v2

    degradation = second_replica.get_degradation_state(
        degradation_key="live_text_generation:"
        + derive_candidate_identity_v2(
            provider_id="text.local",
            model_family="qwen3:8b",
            model_revision="qwen3:8b",
            deployment=None,
        )
    )
    assert degradation is not None
    assert degradation.consecutive_failure_count >= 3
