from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.contracts.model_catalogue import derive_model_catalogue_entry_id
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


def degradation_key_for(identity: str | None = None) -> str:
    """Failure bookkeeping is keyed per CANDIDATE identity (issue #304).

    Issue #176 S3 keyed the breaker per provider so the primary's failures
    could never open the alternate's breaker. The serving policy makes
    same-provider model candidates normal topology, and a model-specific
    failure says nothing about the provider's other models - so the key is
    now the candidate's catalogue entry id (provider:revision[:deployment])
    whenever the execution config names a complete model identity, keeping
    a sibling candidate's health independent. A config with only a provider
    (stub-adjacent shapes) keys by provider; with neither, the bare prefix
    remains the key. Provider-wide outages open each candidate's breaker on
    its own failures - the conservative direction.

    Passing ``identity`` names a candidate (entry id) or provider
    explicitly. Recording a failure or a success omits it: those run inside
    the gateway's per-candidate config override, so the ambient identity is
    already the right one. Reading posture for evidence or an operator view
    happens after that scope has exited and must name the identity it means
    (issue #237).
    """

    if identity:
        return f"{DEGRADATION_KEY_PREFIX}:{identity}"
    config = resolve_provider_execution_config()
    if config.provider_id and config.model_id:
        entry_id = derive_model_catalogue_entry_id(
            provider_id=config.provider_id,
            model_revision=config.model_version or config.model_id,
            deployment=config.deployment,
        )
        return f"{DEGRADATION_KEY_PREFIX}:{entry_id}"
    if config.provider_id:
        return f"{DEGRADATION_KEY_PREFIX}:{config.provider_id}"
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
    identity: str | None = None,
) -> ProviderDegradationStatusDescriptor:
    """Breaker posture for a provider identity.

    ``identity`` names the candidate (entry id) or provider to report on. Evidence for an
    execution must pass the identity that actually SERVED it: the gateway's
    per-candidate config override has already exited by the time evidence is
    built, so resolving the ambient config would report the primary's
    breaker for an alternate-served execution (issue #237).
    """

    state = _resolve_provider_degradation_state(identity)
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
        if state.circuit_open_remaining_seconds is None:
            # The cooldown clock starts when the breaker actually begins
            # refusing traffic. A breaker that opened because its threshold
            # was lowered - rather than because a call failed - carries no
            # deadline yet, and no further failure can arrive to stamp one
            # while it is refusing, so it would stay open forever (#248).
            _open_circuit()
        raise ProviderExecutionError(
            category=ProviderFailureCategory.CIRCUIT_OPEN,
            message=(
                "Live-provider circuit breaker is currently open due to repeated upstream failures."
            ),
        )


def record_provider_failure(category: ProviderFailureCategory) -> None:
    if category not in _tracked_failure_categories():
        return

    _reclaim_elapsed_cooldown()
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
    identity: str | None = None,
) -> ProviderDegradationState:
    findings: list[str] = []
    state_record = _load_degradation_record(identity)
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

    circuit_remaining_seconds = _remaining_circuit_open_seconds(state_record.circuit_open_until)
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

    # A stamped cooldown that has elapsed has already answered for the
    # failures that opened it, so they no longer count toward the posture.
    # The persisted counters are cleared by the next write rather than by
    # this read (#248).
    cooldown_served = state_record.circuit_open_until is not None
    effective_failure_count = 0 if cooldown_served else state_record.consecutive_failure_count
    effective_last_category = None if cooldown_served else state_record.last_failure_category

    if effective_failure_count >= (circuit_threshold or 0):
        # Open without a deadline: the threshold now sits at or below a count
        # that is already recorded. Whoever acts on this - the failure
        # recorder or the enforcing preflight - stamps the cooldown.
        return ProviderDegradationState(
            status="CIRCUIT_OPEN",
            enforcement_enabled=True,
            configuration_valid=True,
            consecutive_failure_count=effective_failure_count,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=effective_last_category,
            timeout_failure_count=state_record.timeout_failure_count,
            rate_limited_failure_count=state_record.rate_limited_failure_count,
            upstream_error_failure_count=state_record.upstream_error_failure_count,
            findings=[
                "Provider circuit breaker is open because the recorded consecutive failures are at or above the configured circuit threshold."
            ],
        )

    if effective_failure_count >= (degraded_threshold or 0):
        return ProviderDegradationState(
            status="DEGRADED_UPSTREAM",
            enforcement_enabled=True,
            configuration_valid=True,
            consecutive_failure_count=effective_failure_count,
            degraded_failure_count_threshold=degraded_threshold,
            circuit_open_failure_count_threshold=circuit_threshold,
            circuit_open_remaining_seconds=None,
            last_failure_category=effective_last_category,
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
        consecutive_failure_count=effective_failure_count,
        degraded_failure_count_threshold=degraded_threshold,
        circuit_open_failure_count_threshold=circuit_threshold,
        circuit_open_remaining_seconds=None,
        last_failure_category=effective_last_category,
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
        findings=[
            "Provider degradation controls are enabled and the live provider path is currently healthy."
        ],
    )


def _remaining_circuit_open_seconds(circuit_open_until: str | None) -> int | None:
    """Seconds left on a stamped cooldown, or None when none remain.

    A pure calculation. It used to clear an elapsed cooldown as a side
    effect, which made every posture read a write and meant inspecting one
    provider could reset another provider's breaker (issues #237, #248).
    Clearing now belongs to ``_reclaim_elapsed_cooldown`` on the write path.
    """

    if circuit_open_until is None:
        return None
    remaining = int((datetime.fromisoformat(circuit_open_until) - _utcnow()).total_seconds())
    return remaining if remaining > 0 else None


def _reclaim_elapsed_cooldown(identity: str | None = None) -> None:
    """Clear a cooldown that has run its course, before a new failure counts.

    The breaker served its cooldown, so the next failure starts a fresh
    budget instead of resuming a count those failures already paid for.
    """

    state_record = _load_degradation_record(identity)
    if state_record.circuit_open_until is None:
        return
    if _remaining_circuit_open_seconds(state_record.circuit_open_until) is not None:
        return
    _save_degradation_record(
        identity=identity,
        consecutive_failure_count=0,
        last_failure_category=None,
        circuit_open_until=None,
        timeout_failure_count=state_record.timeout_failure_count,
        rate_limited_failure_count=state_record.rate_limited_failure_count,
        upstream_error_failure_count=state_record.upstream_error_failure_count,
    )


def _open_circuit(identity: str | None = None) -> None:
    state_record = _load_degradation_record(identity)
    cooldown_seconds = resolve_provider_execution_config().enforcement.circuit_open_seconds or 0
    _save_degradation_record(
        identity=identity,
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
    identity: str | None = None,
) -> ProviderDegradationStateRecord:
    repository = get_provider_operations_store()
    degradation_key = degradation_key_for(identity)
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
    identity: str | None = None,
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
            degradation_key=degradation_key_for(identity),
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
