from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.contracts.providers import (
    ProviderDegradationStatusDescriptor,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.repositories.provider_operations_repository import ProviderDegradationStateRecord
from app.services.provider_operations_store import get_provider_operations_store
from app.services.provider_execution_config import resolve_provider_execution_config

# The bare prefix was the whole key before #176 S3 keyed bookkeeping per
# provider identity, so it is also the shape a pre-migration row still
# carries (issue #234).
DEGRADATION_KEY_PREFIX = "live_text_generation"


def degradation_key_for(provider_id: str | None = None) -> str:
    """Failure bookkeeping is keyed per provider identity (issue #176, S3).

    Ordered fallback requires the primary's failures to never open the
    alternate's breaker, so the key carries the provider identity of the
    execution config in scope - the gateway's per-candidate config override
    selects the candidate being checked or charged. Without a configured
    provider identity (stub and disabled modes) the bare prefix remains the
    key.

    Passing ``provider_id`` names an identity explicitly. Recording a failure
    or a success omits it: those run inside the gateway's per-candidate
    config override, so the ambient identity is already the right one.
    Reading posture for evidence or an operator view happens after that
    scope has exited and must name the identity it means (issue #237).
    """

    resolved = provider_id or resolve_provider_execution_config().provider_id
    if resolved:
        return f"{DEGRADATION_KEY_PREFIX}:{resolved}"
    return DEGRADATION_KEY_PREFIX


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


def build_provider_degradation_status(
    provider_id: str | None = None,
) -> ProviderDegradationStatusDescriptor:
    """Breaker posture for a provider identity.

    ``provider_id`` names the identity to report on. Evidence for an
    execution must pass the identity that actually SERVED it: the gateway's
    per-candidate config override has already exited by the time evidence is
    built, so resolving the ambient config would report the primary's
    breaker for an alternate-served execution (issue #237).
    """

    state = _resolve_provider_degradation_state(provider_id)
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

    repository = get_provider_operations_store()
    repository.record_degradation_failure(
        degradation_key=degradation_key_for(),
        category=category,
        updated_at=_utcnow().isoformat(),
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
    repository = get_provider_operations_store()
    repository.reset_degradation_states()


def _resolve_provider_degradation_state(
    provider_id: str | None = None,
) -> ProviderDegradationState:
    findings: list[str] = []
    state_record = _load_degradation_record(provider_id)
    # Enforcement thresholds are shared across candidates by construction
    # (see derive_fallback_execution_config), so the ambient read is correct
    # here even when the record above belongs to a named identity.
    enforcement = resolve_provider_execution_config().enforcement
    enforcement_enabled = enforcement.degradation_enforced
    degraded_threshold = enforcement.degraded_failure_count_threshold
    circuit_threshold = enforcement.circuit_open_failure_count_threshold
    circuit_open_seconds = enforcement.circuit_open_seconds
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

    circuit_remaining_seconds = _remaining_circuit_open_seconds(
        state_record.circuit_open_until, provider_id=provider_id
    )
    state_record = _load_degradation_record(provider_id)
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
        _open_circuit(provider_id)
        return _resolve_provider_degradation_state(provider_id)

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


def _remaining_circuit_open_seconds(
    circuit_open_until: str | None, *, provider_id: str | None = None
) -> int | None:
    """Remaining cooldown for ``provider_id``, clearing an expired one.

    The clear is a write on a read path, so it has to be keyed to the
    identity being asked about: keyed ambiently, inspecting the alternate's
    posture would reset the primary's breaker (issue #237).
    """

    if circuit_open_until is None:
        return None
    until = datetime.fromisoformat(circuit_open_until)
    remaining = int((until - _utcnow()).total_seconds())
    if remaining > 0:
        return remaining
    state_record = _load_degradation_record(provider_id)
    _save_degradation_record(
        provider_id=provider_id,
        consecutive_failure_count=0,
        last_failure_category=None,
        circuit_open_until=None,
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
    )
    return None


def _open_circuit(provider_id: str | None = None) -> None:
    state_record = _load_degradation_record(provider_id)
    cooldown_seconds = resolve_provider_execution_config().enforcement.circuit_open_seconds or 0
    _save_degradation_record(
        provider_id=provider_id,
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


def _load_degradation_record(
    provider_id: str | None = None,
) -> ProviderDegradationStateRecord:
    repository = get_provider_operations_store()
    degradation_key = degradation_key_for(provider_id)
    record = repository.get_degradation_state(degradation_key=degradation_key)
    if record is not None:
        return record
    return ProviderDegradationStateRecord(
        degradation_key=degradation_key,
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
    provider_id: str | None = None,
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
            degradation_key=degradation_key_for(provider_id),
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
