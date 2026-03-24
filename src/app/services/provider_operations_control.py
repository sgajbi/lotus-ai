from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.providers import (
    ProviderOperationsControlActionRequest,
    ProviderOperationsControlActionResponse,
    ProviderOperationsControlActionType,
    ProviderOperationsControlEventDescriptor,
    ProviderOperationsControlHistoryResponse,
)
from app.repositories.provider_operations_repository import ProviderOperationsEventRecord
from app.repositories.provider_operations_repository import ProviderOperationsRepository
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.provider_budget_policy import _BUDGET_KEY
from app.services.provider_degradation_state import _DEGRADATION_KEY
from app.services.provider_operations_store import get_provider_operations_store


def build_provider_operations_control_history(
    *,
    limit: int = 20,
) -> ProviderOperationsControlHistoryResponse:
    repository = get_provider_operations_store()
    return ProviderOperationsControlHistoryResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        control_plane_store_mode=settings.provider_operations_store_mode,
        reset_actions_supported=_reset_actions_supported(),
        supported_action_types=list(ProviderOperationsControlActionType),
        latest_events=[
            _to_event_descriptor(event)
            for event in repository.list_operations_events(limit=max(limit, 1))
        ],
        notes=[
            "Provider-operations reset actions are explicit control-plane events with operator reason and approver identity recorded durably.",
            "Quota, budget, and degradation resets are intended to replace ad hoc table edits or process restarts as the reviewable recovery path.",
            (
                "Durable reset reviewability is only authoritative when LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE=sqlalchemy."
                if settings.provider_operations_store_mode != "sqlalchemy"
                else "The SQL-backed provider-operations store is currently active, so reset actions are durable and reviewable across restart."
            ),
        ],
    )


def apply_provider_operations_control_action(
    request: ProviderOperationsControlActionRequest,
) -> ProviderOperationsControlActionResponse:
    authorization = require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    if not _reset_actions_supported():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Provider-operations reset actions require LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE=sqlalchemy "
                "so the control-plane event history remains durable and reviewable."
            ),
        )

    _validate_control_action_request(request)
    repository = get_provider_operations_store()
    affected_record_count = _apply_control_action(repository=repository, request=request)
    event = ProviderOperationsEventRecord(
        event_id=f"provider_ops_evt_{uuid4().hex[:12]}",
        action_type=request.action_type,
        scope=request.scope,
        scope_key=request.scope_key,
        reason=request.reason,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        affected_record_count=affected_record_count,
        authorization=authorization,
        recorded_at=_utcnow(),
    )
    repository.save_operations_event(event)
    return ProviderOperationsControlActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        event=_to_event_descriptor(event),
        summary=[
            f"Applied provider-operations action `{request.action_type.value}`.",
            f"Affected provider-operations record count: {affected_record_count}.",
            f"Action requested by `{request.requested_by}` and approved by `{request.approved_by}`.",
        ],
    )


def _apply_control_action(
    *,
    repository: ProviderOperationsRepository,
    request: ProviderOperationsControlActionRequest,
) -> int:
    if request.action_type == ProviderOperationsControlActionType.RESET_ALL_QUOTAS:
        return repository.reset_quota_states()
    if request.action_type == ProviderOperationsControlActionType.RESET_QUOTA_SCOPE:
        return repository.reset_quota_states(scope=request.scope, scope_key=request.scope_key)
    if request.action_type == ProviderOperationsControlActionType.RESET_BUDGET:
        return repository.reset_budget_state(budget_key=_BUDGET_KEY)
    if request.action_type == ProviderOperationsControlActionType.RESET_DEGRADATION:
        return repository.reset_degradation_state(degradation_key=_DEGRADATION_KEY)
    if request.action_type == ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS:
        return (
            repository.reset_quota_states()
            + repository.reset_budget_state(budget_key=_BUDGET_KEY)
            + repository.reset_degradation_state(degradation_key=_DEGRADATION_KEY)
        )
    raise RuntimeError("Unsupported provider-operations control action.")


def _validate_control_action_request(request: ProviderOperationsControlActionRequest) -> None:
    if request.action_type == ProviderOperationsControlActionType.RESET_QUOTA_SCOPE:
        if request.scope is None or request.scope_key is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "RESET_QUOTA_SCOPE requires both `scope` and `scope_key` so the targeted quota reset remains explicit."
                ),
            )
        return

    if request.scope is not None or request.scope_key is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{request.action_type.value} does not accept `scope` or `scope_key`; use RESET_QUOTA_SCOPE for targeted quota resets."
            ),
        )


def _to_event_descriptor(
    event: ProviderOperationsEventRecord,
) -> ProviderOperationsControlEventDescriptor:
    return ProviderOperationsControlEventDescriptor(
        event_id=event.event_id,
        action_type=event.action_type,
        scope=event.scope,
        scope_key=event.scope_key,
        reason=event.reason,
        requested_by=event.requested_by,
        approved_by=event.approved_by,
        affected_record_count=event.affected_record_count,
        authorization=event.authorization,
        recorded_at=event.recorded_at,
    )


def _reset_actions_supported() -> bool:
    return settings.provider_operations_store_mode == "sqlalchemy"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
