"""Kill-switch operator actions and enforcement (issue #177, slice 1).

Activation and clearance are governed control-plane actions with opposite
risk directions (issue #157). Activation stops execution: one authorized
principal, immediately - never a human handoff inside an emergency stop.
Clearance resumes execution somebody judged unsafe: a verified requester
records the intent, a DISTINCT verified credential approves the exact action
hash, and the evidence chain is durable. Both require PROVIDER_CONTROL
authorization and (like provider-operations resets) a durable store so the
control history survives restarts and replicas. Enforcement runs at the provider gateway
preflight, before any other veto: an operator stop outranks quota, budget and
breaker state, and a hit is recorded as a routing rejection with the bounded
KILL_SWITCH_ACTIVE category (issue #176).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionType,
)
from app.contracts.kill_switches import (
    KillSwitchSemantics,
    TARGETLESS_KILL_SWITCH_SCOPES,
    KillSwitchActionResponse,
    KillSwitchActivationRecord,
    KillSwitchActivationRequest,
    KillSwitchClearApprovalRequest,
    KillSwitchClearApprovalResponse,
    KillSwitchClearIntentRequest,
    KillSwitchScope,
    KillSwitchStatusResponse,
)
from app.contracts.providers import ProviderExecutionRequest, ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.kill_switch_store import get_kill_switch_repository
from app.services.provider_metrics import record_kill_switch_action
from app.services.provider_execution_config import resolve_provider_execution_config


def activate_kill_switch(request: KillSwitchActivationRequest) -> KillSwitchActionResponse:
    require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    _require_durable_store()
    if request.scope in TARGETLESS_KILL_SWITCH_SCOPES:
        if request.target is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Scope {request.scope.value} is targetless; do not supply a target.",
            )
    elif not request.target:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Scope {request.scope.value} requires an explicit target.",
        )
    if request.expires_at_utc is not None:
        _require_valid_utc_instant(request.expires_at_utc)

    activation = KillSwitchActivationRecord(
        switch_id=f"ksw_{uuid4().hex[:16]}",
        scope=request.scope,
        semantics=request.semantics,
        target=request.target,
        reason=request.reason,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        activated_at=_utc_now_iso(),
        expires_at_utc=request.expires_at_utc,
    )
    get_kill_switch_repository().upsert_activation(activation)
    record_kill_switch_action(
        action="activated", scope=activation.scope.value, semantics=activation.semantics.value
    )
    return KillSwitchActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.kill_switch_store_mode,
        activation=activation,
        summary=[
            f"Activated kill switch `{activation.switch_id}` for scope "
            f"`{activation.scope.value}`"
            + (f" target `{activation.target}`." if activation.target else "."),
            f"Requested by `{request.requested_by}` and approved by `{request.approved_by}`.",
            "New live text executions in scope are refused immediately (hard kill).",
        ],
    )


def request_kill_switch_clearance(
    switch_id: str,
    request: KillSwitchClearIntentRequest,
    caller: AuthenticatedCaller,
) -> GovernedActionResponse:
    """Step one of governed clearance: record the intent under the requester's credential."""

    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    _require_durable_store()
    activation = _require_active_activation(switch_id)
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.KILL_SWITCH_CLEAR,
        target=switch_id,
        payload=_clearance_payload(activation, request.reason),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Clearance of kill switch `{switch_id}` is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            "The switch keeps enforcing until the approval executes.",
        ],
    )


def approve_kill_switch_clearance(
    switch_id: str,
    request: KillSwitchClearApprovalRequest,
    caller: AuthenticatedCaller,
) -> KillSwitchClearApprovalResponse:
    """Step two: a distinct verified credential approves the exact action, which executes it."""

    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    _require_durable_store()
    repository = get_kill_switch_repository()
    activation = _require_active_activation(switch_id)
    cleared_holder: dict[str, KillSwitchActivationRecord] = {}

    def _execute_clearance(record: GovernedActionRecord) -> None:
        cleared = activation.model_copy(
            update={
                "cleared_at": _utc_now_iso(),
                "cleared_by": f"{caller.caller_app} (credential {caller.credential_key_id})",
                "clear_reason": record.action_payload.get("clear_reason"),
            }
        )
        repository.upsert_activation(cleared)
        record_kill_switch_action(
            action="cleared", scope=cleared.scope.value, semantics=cleared.semantics.value
        )
        cleared_holder["activation"] = cleared

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=switch_id,
        expected_hash=request.action_hash,
        current_payload_builder=lambda record: _clearance_payload(
            activation, record.action_payload.get("clear_reason") or ""
        ),
        attribution=request.approved_by,
        execute=_execute_clearance,
    )
    return KillSwitchClearApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.kill_switch_store_mode,
        activation=cleared_holder["activation"],
        governed_action=executed,
        summary=[
            f"Cleared kill switch `{switch_id}` under governed action `{executed.action_id}`.",
            f"Requested under credential `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}`.",
        ],
    )


def _require_active_activation(switch_id: str) -> KillSwitchActivationRecord:
    activation = get_kill_switch_repository().get_activation(switch_id)
    if activation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No kill-switch activation exists for `{switch_id}`.",
        )
    if activation.cleared_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Kill-switch activation `{switch_id}` is already cleared.",
        )
    return activation


def _clearance_payload(
    activation: KillSwitchActivationRecord, reason: str
) -> dict[str, str | None]:
    """The exact action the approver signs off on.

    Pins the activation identity (`activated_at`) as well as the switch id, so
    an approval can never carry over to a re-activation of the same switch.
    """

    return {
        "action_type": GovernedActionType.KILL_SWITCH_CLEAR.value,
        "switch_id": activation.switch_id,
        "scope": activation.scope.value,
        "semantics": activation.semantics.value,
        "target": activation.target,
        "activated_at": activation.activated_at,
        "clear_reason": reason,
    }


def build_kill_switch_status() -> KillSwitchStatusResponse:
    now = _utc_now_iso()
    activations = [
        _record_expiry_if_lapsed(activation, now=now)
        for activation in get_kill_switch_repository().list_activations()
    ]
    return KillSwitchStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.kill_switch_store_mode,
        expired_count=sum(
            1 for activation in activations if activation.expiry_recorded_at is not None
        ),
        active_count=sum(1 for activation in activations if _is_enforcing(activation, now=now)),
        activations=activations,
    )


def _record_expiry_if_lapsed(
    activation: KillSwitchActivationRecord, *, now: str
) -> KillSwitchActivationRecord:
    """Durably record the expiry event for a lapsed, uncleared activation.

    Sweep-on-read: deterministic, replica-safe (idempotent marker upsert), and
    requires no scheduler. The switch is inert from expires_at_utc regardless;
    this marks the recorded event and feeds the expiry counter exactly once.
    """

    if (
        activation.cleared_at is not None
        or activation.expiry_recorded_at is not None
        or activation.expires_at_utc is None
        or _parse_utc(activation.expires_at_utc) > _parse_utc(now)
    ):
        return activation
    expired = activation.model_copy(update={"expiry_recorded_at": now})
    get_kill_switch_repository().upsert_activation(expired)
    record_kill_switch_action(
        action="expired", scope=expired.scope.value, semantics=expired.semantics.value
    )
    return expired


_drain_completion_permitted: ContextVar[bool] = ContextVar(
    "lotus_ai_kill_switch_drain_completion_permitted", default=False
)


@contextmanager
def drain_completion_permit() -> Iterator[None]:
    """Mark this execution as the safe completion of already-claimed async work.

    Under the permit, DRAIN activations do not refuse execution - that is the
    entire meaning of drain. HARD_KILL refuses regardless.
    """

    token = _drain_completion_permitted.set(True)
    try:
        yield
    finally:
        _drain_completion_permitted.reset(token)


def enforce_kill_switch_intake(
    *,
    task_id: str,
    tenant_id: str | None,
    caller_app: str,
) -> None:
    """Refuse new async intake in scope of any enforcing activation.

    Intake stops under BOTH semantics: draining means no new work enters the
    queue while claimed work completes. Provider/model scopes match the
    currently configured live identity, exactly as the sync preflight does.
    """

    probe = ProviderExecutionRequest.model_construct(
        task_id=task_id,
        tenant_id=tenant_id,
        caller_app=caller_app,
    )
    now = _utc_now_iso()
    for activation in get_kill_switch_repository().list_activations():
        if not _is_enforcing(activation, now=now):
            continue
        if not _matches(activation, request=probe):
            continue
        record_kill_switch_action(
            action="refused_intake",
            scope=activation.scope.value,
            semantics=activation.semantics.value,
        )
        target_note = f" target `{activation.target}`" if activation.target else ""
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{ProviderFailureCategory.KILL_SWITCH_ACTIVE.value}: kill switch "
                f"`{activation.switch_id}` ({activation.semantics.value}) is active for "
                f"scope `{activation.scope.value}`{target_note}; new async intake is "
                "refused until it clears."
            ),
        )


def enforce_kill_switches(request: ProviderExecutionRequest) -> None:
    """Refuse live execution when any enforcing activation matches the request.

    Called first among the gateway's live preflight checks: an operator stop
    outranks quota, budget and breaker state. Raises with the bounded
    KILL_SWITCH_ACTIVE category, which issue #176 records as the candidate's
    rejection reason.
    """

    now = _utc_now_iso()
    for activation in get_kill_switch_repository().list_activations():
        if not _is_enforcing(activation, now=now):
            continue
        if _matches(activation, request=request):
            if (
                activation.semantics is KillSwitchSemantics.DRAIN
                and _drain_completion_permitted.get()
            ):
                # Draining: already-claimed async work completes safely.
                continue
            record_kill_switch_action(
                action="refused_sync",
                scope=activation.scope.value,
                semantics=activation.semantics.value,
            )
            target_note = f" target `{activation.target}`" if activation.target else ""
            raise ProviderExecutionError(
                category=ProviderFailureCategory.KILL_SWITCH_ACTIVE,
                message=(
                    f"Kill switch `{activation.switch_id}` is active for scope "
                    f"`{activation.scope.value}`{target_note}: {activation.reason}"
                ),
            )


def _matches(activation: KillSwitchActivationRecord, *, request: ProviderExecutionRequest) -> bool:
    if activation.scope is KillSwitchScope.ALL_LIVE_TEXT:
        return True
    if activation.scope is KillSwitchScope.PROVIDER:
        return activation.target == resolve_provider_execution_config().provider_id
    if activation.scope is KillSwitchScope.MODEL_REVISION:
        config = resolve_provider_execution_config()
        return activation.target == (config.model_version or config.model_id)
    if activation.scope is KillSwitchScope.TASK:
        return activation.target == request.task_id
    if activation.scope is KillSwitchScope.TENANT:
        return request.tenant_id is not None and activation.target == request.tenant_id
    if activation.scope is KillSwitchScope.CALLER_APP:
        return activation.target == request.caller_app
    raise RuntimeError("Unsupported kill-switch scope.")


def _is_enforcing(activation: KillSwitchActivationRecord, *, now: str) -> bool:
    if activation.cleared_at is not None:
        return False
    if activation.expires_at_utc is not None:
        return _parse_utc(activation.expires_at_utc) > _parse_utc(now)
    return True


def _require_durable_store() -> None:
    if settings.kill_switch_store_mode != "sqlalchemy":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Kill-switch actions require LOTUS_AI_KILL_SWITCH_STORE_MODE=sqlalchemy so "
                "activations survive restarts and are shared across replicas."
            ),
        )


def _require_valid_utc_instant(value: str) -> None:
    try:
        _parse_utc(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="expires_at_utc must be a UTC ISO-8601 instant.",
        ) from exc


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
