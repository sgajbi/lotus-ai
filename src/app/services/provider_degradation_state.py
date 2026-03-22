from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.contracts.providers import (
    ProviderDegradationStatusDescriptor,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError

_FAILURE_COUNTS: dict[ProviderFailureCategory, int] = {
    ProviderFailureCategory.PROVIDER_TIMEOUT: 0,
    ProviderFailureCategory.PROVIDER_RATE_LIMITED: 0,
    ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR: 0,
}
_CONSECUTIVE_FAILURE_COUNT = 0
_LAST_FAILURE_CATEGORY: ProviderFailureCategory | None = None
_CIRCUIT_OPEN_UNTIL: datetime | None = None


@dataclass(frozen=True)
class ProviderDegradationState:
    status: str
    enforcement_enabled: bool
    configuration_valid: bool
    consecutive_failure_count: int
    degraded_failure_count_threshold: int | None
    circuit_open_failure_count_threshold: int | None
    circuit_open_remaining_seconds: int | None
    last_failure_category: ProviderFailureCategory | None
    timeout_failure_count: int
    rate_limited_failure_count: int
    upstream_error_failure_count: int
    findings: list[str]


def build_provider_degradation_status() -> ProviderDegradationStatusDescriptor:
    state = _resolve_provider_degradation_state()
    return ProviderDegradationStatusDescriptor(
        status=state.status,
        enforcement_enabled=state.enforcement_enabled,
        configuration_valid=state.configuration_valid,
        consecutive_failure_count=state.consecutive_failure_count,
        degraded_failure_count_threshold=state.degraded_failure_count_threshold,
        circuit_open_failure_count_threshold=state.circuit_open_failure_count_threshold,
        circuit_open_remaining_seconds=state.circuit_open_remaining_seconds,
        last_failure_category=state.last_failure_category,
        timeout_failure_count=state.timeout_failure_count,
        rate_limited_failure_count=state.rate_limited_failure_count,
        upstream_error_failure_count=state.upstream_error_failure_count,
        findings=state.findings,
    )


def enforce_provider_degradation_preflight() -> None:
    state = _resolve_provider_degradation_state()
    if not state.enforcement_enabled:
        return
    if not state.configuration_valid:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.CIRCUIT_OPEN,
            message=(
                "Live-provider degradation controls are configured inconsistently and cannot be enforced safely."
            ),
        )
    if state.status == "CIRCUIT_OPEN":
        raise ProviderExecutionError(
            category=ProviderFailureCategory.CIRCUIT_OPEN,
            message=(
                "Live-provider circuit breaker is currently open due to repeated upstream failures."
            ),
        )


def record_provider_failure(category: ProviderFailureCategory) -> None:
    global _CONSECUTIVE_FAILURE_COUNT, _LAST_FAILURE_CATEGORY
    if category not in _FAILURE_COUNTS:
        return
    _FAILURE_COUNTS[category] += 1
    _CONSECUTIVE_FAILURE_COUNT += 1
    _LAST_FAILURE_CATEGORY = category
    state = _resolve_provider_degradation_state()
    if state.enforcement_enabled and state.configuration_valid and state.status == "CIRCUIT_OPEN":
        _open_circuit()


def record_successful_provider_execution() -> None:
    global _CONSECUTIVE_FAILURE_COUNT, _LAST_FAILURE_CATEGORY, _CIRCUIT_OPEN_UNTIL
    _CONSECUTIVE_FAILURE_COUNT = 0
    _LAST_FAILURE_CATEGORY = None
    _CIRCUIT_OPEN_UNTIL = None


def reset_provider_degradation_state() -> None:
    global _CONSECUTIVE_FAILURE_COUNT, _LAST_FAILURE_CATEGORY, _CIRCUIT_OPEN_UNTIL
    for key in _FAILURE_COUNTS:
        _FAILURE_COUNTS[key] = 0
    _CONSECUTIVE_FAILURE_COUNT = 0
    _LAST_FAILURE_CATEGORY = None
    _CIRCUIT_OPEN_UNTIL = None


def _resolve_provider_degradation_state() -> ProviderDegradationState:
    findings: list[str] = []
    enforcement_enabled = settings.live_text_degradation_enforced
    degraded_threshold = settings.live_text_degraded_failure_count_threshold
    circuit_threshold = settings.live_text_circuit_open_failure_count_threshold
    circuit_open_seconds = settings.live_text_circuit_open_seconds
    configuration_valid = True

    if not enforcement_enabled:
        return ProviderDegradationState(
            status="DOCUMENTED_ONLY",
            enforcement_enabled=False,
            configuration_valid=True,
            consecutive_failure_count=_CONSECUTIVE_FAILURE_COUNT,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=_LAST_FAILURE_CATEGORY,
            timeout_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_TIMEOUT],
            rate_limited_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_RATE_LIMITED],
            upstream_error_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR],
            findings=[
                "Provider degradation and circuit-breaker posture remain documented-only until degradation controls are explicitly enabled."
            ],
        )

    if degraded_threshold is None or degraded_threshold <= 0:
        configuration_valid = False
        findings.append(
            "Provider degradation enforcement requires a positive degraded failure-count threshold."
        )
    if circuit_threshold is None or circuit_threshold <= 0:
        configuration_valid = False
        findings.append(
            "Provider degradation enforcement requires a positive circuit-open failure-count threshold."
        )
    if (
        degraded_threshold is not None
        and circuit_threshold is not None
        and degraded_threshold > circuit_threshold
    ):
        configuration_valid = False
        findings.append(
            "Provider degraded failure-count threshold must not exceed the circuit-open threshold."
        )
    if circuit_open_seconds is None or circuit_open_seconds < 0:
        configuration_valid = False
        findings.append(
            "Provider circuit-open cooldown must be zero or a positive number of seconds."
        )

    if not configuration_valid:
        return ProviderDegradationState(
            status="INVALID",
            enforcement_enabled=True,
            configuration_valid=False,
            consecutive_failure_count=_CONSECUTIVE_FAILURE_COUNT,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=_LAST_FAILURE_CATEGORY,
            timeout_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_TIMEOUT],
            rate_limited_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_RATE_LIMITED],
            upstream_error_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR],
            findings=findings,
        )

    circuit_remaining_seconds = _remaining_circuit_open_seconds()
    if circuit_remaining_seconds is not None:
        return ProviderDegradationState(
            status="CIRCUIT_OPEN",
            enforcement_enabled=True,
            configuration_valid=True,
            consecutive_failure_count=_CONSECUTIVE_FAILURE_COUNT,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=circuit_remaining_seconds,
            last_failure_category=_LAST_FAILURE_CATEGORY,
            timeout_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_TIMEOUT],
            rate_limited_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_RATE_LIMITED],
            upstream_error_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR],
            findings=[
                "Provider circuit breaker is currently open because repeated upstream failures crossed the configured circuit threshold."
            ],
        )

    if _CONSECUTIVE_FAILURE_COUNT >= (circuit_threshold or 0):
        _open_circuit()
        return _resolve_provider_degradation_state()

    if _CONSECUTIVE_FAILURE_COUNT >= (degraded_threshold or 0):
        return ProviderDegradationState(
            status="DEGRADED_UPSTREAM",
            enforcement_enabled=True,
            configuration_valid=True,
            consecutive_failure_count=_CONSECUTIVE_FAILURE_COUNT,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=_LAST_FAILURE_CATEGORY,
            timeout_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_TIMEOUT],
            rate_limited_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_RATE_LIMITED],
            upstream_error_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR],
            findings=[
                "Provider upstream is currently degraded because consecutive failures crossed the configured degraded threshold."
            ],
        )

    return ProviderDegradationState(
        status="NORMAL",
        enforcement_enabled=True,
        configuration_valid=True,
        consecutive_failure_count=_CONSECUTIVE_FAILURE_COUNT,
        degraded_failure_count_threshold=degraded_threshold,
        circuit_open_failure_count_threshold=circuit_threshold,
        circuit_open_remaining_seconds=None,
        last_failure_category=_LAST_FAILURE_CATEGORY,
        timeout_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_TIMEOUT],
        rate_limited_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_RATE_LIMITED],
        upstream_error_failure_count=_FAILURE_COUNTS[ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR],
        findings=["Provider degradation controls are enabled and the live provider path is currently healthy."],
    )


def _remaining_circuit_open_seconds() -> int | None:
    global _CIRCUIT_OPEN_UNTIL, _CONSECUTIVE_FAILURE_COUNT, _LAST_FAILURE_CATEGORY
    if _CIRCUIT_OPEN_UNTIL is None:
        return None
    remaining = int((_CIRCUIT_OPEN_UNTIL - _utcnow()).total_seconds())
    if remaining > 0:
        return remaining
    _CIRCUIT_OPEN_UNTIL = None
    _CONSECUTIVE_FAILURE_COUNT = 0
    _LAST_FAILURE_CATEGORY = None
    return None


def _open_circuit() -> None:
    global _CIRCUIT_OPEN_UNTIL
    cooldown_seconds = settings.live_text_circuit_open_seconds or 0
    _CIRCUIT_OPEN_UNTIL = _utcnow() + timedelta(seconds=cooldown_seconds)


def _utcnow() -> datetime:
    return datetime.now(UTC)
