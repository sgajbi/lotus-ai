from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.contracts.providers import (
    ProviderDegradationStatusDescriptor,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.repositories.provider_operations_repository import ProviderDegradationStateRecord
from app.services.provider_operations_store import get_provider_operations_store

_DEGRADATION_KEY = "live_text_generation"


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
    if category not in _tracked_failure_categories():
        return

    state_record = _load_degradation_record()
    timeout_count = state_record.timeout_failure_count
    rate_limited_count = state_record.rate_limited_failure_count
    upstream_error_count = state_record.upstream_error_failure_count
    if category == ProviderFailureCategory.PROVIDER_TIMEOUT:
        timeout_count += 1
    elif category == ProviderFailureCategory.PROVIDER_RATE_LIMITED:
        rate_limited_count += 1
    elif category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR:
        upstream_error_count += 1

    _save_degradation_record(
        consecutive_failure_count=state_record.consecutive_failure_count + 1,
        last_failure_category=category,
        circuit_open_until=state_record.circuit_open_until,
        timeout_failure_count=timeout_count,
        rate_limited_failure_count=rate_limited_count,
        upstream_error_failure_count=upstream_error_count,
    )
    state = _resolve_provider_degradation_state()
    if state.enforcement_enabled and state.configuration_valid and state.status == "CIRCUIT_OPEN":
        _open_circuit()


def record_successful_provider_execution() -> None:
    state_record = _load_degradation_record()
    _save_degradation_record(
        consecutive_failure_count=0,
        last_failure_category=None,
        circuit_open_until=None,
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
    )


def reset_provider_degradation_state() -> None:
    _save_degradation_record(
        consecutive_failure_count=0,
        last_failure_category=None,
        circuit_open_until=None,
        timeout_failure_count=0,
        rate_limited_failure_count=0,
        upstream_error_failure_count=0,
    )


def _resolve_provider_degradation_state() -> ProviderDegradationState:
    findings: list[str] = []
    state_record = _load_degradation_record()
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
            consecutive_failure_count=state_record.consecutive_failure_count,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=state_record.last_failure_category,
            timeout_failure_count=state_record.timeout_failure_count,
            rate_limited_failure_count=state_record.rate_limited_failure_count,
            upstream_error_failure_count=state_record.upstream_error_failure_count,
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
            consecutive_failure_count=state_record.consecutive_failure_count,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=state_record.last_failure_category,
            timeout_failure_count=state_record.timeout_failure_count,
            rate_limited_failure_count=state_record.rate_limited_failure_count,
            upstream_error_failure_count=state_record.upstream_error_failure_count,
            findings=findings,
        )

    circuit_remaining_seconds = _remaining_circuit_open_seconds(state_record.circuit_open_until)
    state_record = _load_degradation_record()
    if circuit_remaining_seconds is not None:
        return ProviderDegradationState(
            status="CIRCUIT_OPEN",
            enforcement_enabled=True,
            configuration_valid=True,
            consecutive_failure_count=state_record.consecutive_failure_count,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=circuit_remaining_seconds,
            last_failure_category=state_record.last_failure_category,
            timeout_failure_count=state_record.timeout_failure_count,
            rate_limited_failure_count=state_record.rate_limited_failure_count,
            upstream_error_failure_count=state_record.upstream_error_failure_count,
            findings=[
                "Provider circuit breaker is currently open because repeated upstream failures crossed the configured circuit threshold."
            ],
        )

    if state_record.consecutive_failure_count >= (circuit_threshold or 0):
        _open_circuit()
        return _resolve_provider_degradation_state()

    if state_record.consecutive_failure_count >= (degraded_threshold or 0):
        return ProviderDegradationState(
            status="DEGRADED_UPSTREAM",
            enforcement_enabled=True,
            configuration_valid=True,
            consecutive_failure_count=state_record.consecutive_failure_count,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=state_record.last_failure_category,
            timeout_failure_count=state_record.timeout_failure_count,
            rate_limited_failure_count=state_record.rate_limited_failure_count,
            upstream_error_failure_count=state_record.upstream_error_failure_count,
            findings=[
                "Provider upstream is currently degraded because consecutive failures crossed the configured degraded threshold."
            ],
        )

    return ProviderDegradationState(
        status="NORMAL",
        enforcement_enabled=True,
        configuration_valid=True,
        consecutive_failure_count=state_record.consecutive_failure_count,
        degraded_failure_count_threshold=degraded_threshold,
        circuit_open_failure_count_threshold=circuit_threshold,
        circuit_open_remaining_seconds=None,
        last_failure_category=state_record.last_failure_category,
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
        findings=[
            "Provider degradation controls are enabled and the live provider path is currently healthy."
        ],
    )


def _remaining_circuit_open_seconds(circuit_open_until: str | None) -> int | None:
    if circuit_open_until is None:
        return None
    until = datetime.fromisoformat(circuit_open_until)
    remaining = int((until - _utcnow()).total_seconds())
    if remaining > 0:
        return remaining
    state_record = _load_degradation_record()
    _save_degradation_record(
        consecutive_failure_count=0,
        last_failure_category=None,
        circuit_open_until=None,
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
    )
    return None


def _open_circuit() -> None:
    state_record = _load_degradation_record()
    cooldown_seconds = settings.live_text_circuit_open_seconds or 0
    _save_degradation_record(
        consecutive_failure_count=state_record.consecutive_failure_count,
        last_failure_category=state_record.last_failure_category,
        circuit_open_until=(_utcnow() + timedelta(seconds=cooldown_seconds)).isoformat(),
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
    )


def _tracked_failure_categories() -> set[ProviderFailureCategory]:
    return {
        ProviderFailureCategory.PROVIDER_TIMEOUT,
        ProviderFailureCategory.PROVIDER_RATE_LIMITED,
        ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
    }


def _load_degradation_record() -> ProviderDegradationStateRecord:
    repository = get_provider_operations_store()
    record = repository.get_degradation_state(degradation_key=_DEGRADATION_KEY)
    if record is not None:
        return record
    return ProviderDegradationStateRecord(
        degradation_key=_DEGRADATION_KEY,
        consecutive_failure_count=0,
        last_failure_category=None,
        circuit_open_until=None,
        timeout_failure_count=0,
        rate_limited_failure_count=0,
        upstream_error_failure_count=0,
        updated_at=_utcnow().isoformat(),
    )


def _save_degradation_record(
    *,
    consecutive_failure_count: int,
    last_failure_category: ProviderFailureCategory | None,
    circuit_open_until: str | None,
    timeout_failure_count: int,
    rate_limited_failure_count: int,
    upstream_error_failure_count: int,
) -> None:
    repository = get_provider_operations_store()
    repository.save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key=_DEGRADATION_KEY,
            consecutive_failure_count=consecutive_failure_count,
            last_failure_category=last_failure_category,
            circuit_open_until=circuit_open_until,
            timeout_failure_count=timeout_failure_count,
            rate_limited_failure_count=rate_limited_failure_count,
            upstream_error_failure_count=upstream_error_failure_count,
            updated_at=_utcnow().isoformat(),
        )
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)
