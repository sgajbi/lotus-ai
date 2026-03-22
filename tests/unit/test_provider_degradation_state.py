from datetime import UTC, datetime, timedelta

from pytest import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.services.provider_degradation_state import (
    build_provider_degradation_status,
    enforce_provider_degradation_preflight,
    record_provider_failure,
    record_successful_provider_execution,
)
from app.providers.base import ProviderExecutionError


def test_provider_degradation_status_reports_documented_only_by_default() -> None:
    status = build_provider_degradation_status()

    assert status.status == "DOCUMENTED_ONLY"
    assert status.enforcement_enabled is False
    assert status.configuration_valid is True
    assert status.consecutive_failure_count == 0


def test_provider_degradation_status_reports_degraded_after_threshold() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 3
    settings.live_text_circuit_open_seconds = 60

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_RATE_LIMITED)

    status = build_provider_degradation_status()

    assert status.status == "DEGRADED_UPSTREAM"
    assert status.consecutive_failure_count == 2
    assert status.timeout_failure_count == 1
    assert status.rate_limited_failure_count == 1


def test_provider_degradation_status_reports_circuit_open_after_threshold(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 3
    settings.live_text_circuit_open_seconds = 60
    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_RATE_LIMITED)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)

    status = build_provider_degradation_status()

    assert status.status == "CIRCUIT_OPEN"
    assert status.circuit_open_remaining_seconds == 60
    assert status.last_failure_category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR

    try:
        enforce_provider_degradation_preflight()
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.CIRCUIT_OPEN
    else:
        raise AssertionError("Expected circuit-open preflight rejection")


def test_provider_degradation_status_resets_after_successful_execution(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    assert build_provider_degradation_status().status == "DEGRADED_UPSTREAM"

    record_successful_provider_execution()

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0


def test_provider_degradation_status_resets_after_circuit_cooldown(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 30
    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    assert build_provider_degradation_status().status == "CIRCUIT_OPEN"

    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now + timedelta(seconds=31),
    )

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0


def test_provider_degradation_preflight_rejects_invalid_configuration() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 2
    settings.live_text_circuit_open_failure_count_threshold = 1
    settings.live_text_circuit_open_seconds = -1

    status = build_provider_degradation_status()

    assert status.status == "INVALID"
    assert status.configuration_valid is False

    try:
        enforce_provider_degradation_preflight()
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.CIRCUIT_OPEN
    else:
        raise AssertionError("Expected invalid degradation configuration to block execution")


def test_provider_degradation_status_rejects_missing_circuit_threshold() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 0
    settings.live_text_circuit_open_seconds = 60

    status = build_provider_degradation_status()

    assert status.status == "INVALID"
    assert any("circuit-open failure-count threshold" in finding for finding in status.findings)


def test_provider_degradation_status_rejects_degraded_threshold_above_circuit_threshold() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 3
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60

    status = build_provider_degradation_status()

    assert status.status == "INVALID"
    assert any(
        "must not exceed the circuit-open threshold" in finding for finding in status.findings
    )


def test_provider_degradation_ignores_untracked_failure_categories() -> None:
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60

    record_provider_failure(ProviderFailureCategory.CIRCUIT_OPEN)

    status = build_provider_degradation_status()

    assert status.status == "NORMAL"
    assert status.consecutive_failure_count == 0
