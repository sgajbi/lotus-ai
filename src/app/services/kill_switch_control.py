"""Kill-switch operator actions and enforcement (issue #177, slice 1).

Activation and clearance are governed control-plane actions: PROVIDER_CONTROL
authorization, requester and approver identity, an operator reason, and (like
provider-operations resets) a durable store requirement so the control history
survives restarts and replicas. Enforcement runs at the provider gateway
preflight, before any other veto: an operator stop outranks quota, budget and
breaker state, and a hit is recorded as a routing rejection with the bounded
KILL_SWITCH_ACTIVE category (issue #176).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.kill_switches import (
    TARGETLESS_KILL_SWITCH_SCOPES,
    KillSwitchActionResponse,
    KillSwitchActivationRecord,
    KillSwitchActivationRequest,
    KillSwitchClearRequest,
    KillSwitchScope,
    KillSwitchStatusResponse,
)
from app.contracts.providers import ProviderExecutionRequest, ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.kill_switch_store import get_kill_switch_repository


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
        target=request.target,
        reason=request.reason,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        activated_at=_utc_now_iso(),
        expires_at_utc=request.expires_at_utc,
    )
    get_kill_switch_repository().upsert_activation(activation)
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


def clear_kill_switch(switch_id: str, request: KillSwitchClearRequest) -> KillSwitchActionResponse:
    require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    _require_durable_store()
    repository = get_kill_switch_repository()
    activation = repository.get_activation(switch_id)
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
    cleared = activation.model_copy(
        update={
            "cleared_at": _utc_now_iso(),
            "cleared_by": request.approved_by,
            "clear_reason": request.reason,
        }
    )
    repository.upsert_activation(cleared)
    return KillSwitchActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.kill_switch_store_mode,
        activation=cleared,
        summary=[
            f"Cleared kill switch `{switch_id}`.",
            f"Requested by `{request.requested_by}` and approved by `{request.approved_by}`.",
        ],
    )


def build_kill_switch_status() -> KillSwitchStatusResponse:
    activations = get_kill_switch_repository().list_activations()
    now = _utc_now_iso()
    return KillSwitchStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.kill_switch_store_mode,
        active_count=sum(1 for activation in activations if _is_enforcing(activation, now=now)),
        activations=activations,
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
        return activation.target == settings.live_text_provider_id
    if activation.scope is KillSwitchScope.MODEL_REVISION:
        return activation.target == (
            settings.live_text_model_version or settings.live_text_model_id
        )
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
