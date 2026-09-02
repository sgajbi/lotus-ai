from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionType,
)
from app.contracts.providers import ProviderQuotaScope
from app.contracts.provider_operations import (
    ProviderOperationsControlActionType,
    ProviderOperationsControlEventDescriptor,
    ProviderOperationsControlHistoryResponse,
    ProviderOperationsResetApprovalRequest,
    ProviderOperationsResetApprovalResponse,
    ProviderOperationsResetIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.repositories.provider_operations_repository import ProviderOperationsEventRecord
from app.repositories.provider_operations_repository import ProviderOperationsRepository
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.provider_budget_policy import _BUDGET_KEY
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


def request_provider_operations_reset(
    request: ProviderOperationsResetIntentRequest,
    caller: AuthenticatedCaller,
) -> GovernedActionResponse:
    """Step one of a governed reset: record the intent under the requester's credential.

    The reset shape is validated first, so a pending action is never parked on
    a malformed reset.
    """

    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    _require_durable_reset_plane()
    _validate_reset_shape(
        action_type=request.action_type, scope=request.scope, scope_key=request.scope_key
    )
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.PROVIDER_OPERATIONS_RESET,
        target=_reset_target(
            action_type=request.action_type, scope=request.scope, scope_key=request.scope_key
        ),
        payload=_reset_payload(
            action_type=request.action_type,
            scope=request.scope,
            scope_key=request.scope_key,
            reason=request.reason,
        ),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Reset `{request.action_type.value}` is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            "No provider-operations state changes until the approval executes.",
        ],
    )


def approve_provider_operations_reset(
    request: ProviderOperationsResetApprovalRequest,
    caller: AuthenticatedCaller,
) -> ProviderOperationsResetApprovalResponse:
    """Step two: a distinct verified credential approves the exact reset, which executes it."""

    authorization = require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )
    _require_durable_reset_plane()
    outcome: dict[str, object] = {}

    def _execute_reset(record: GovernedActionRecord) -> None:
        action_type = ProviderOperationsControlActionType(
            str(record.action_payload.get("action_type"))
        )
        raw_scope = record.action_payload.get("scope")
        scope = ProviderQuotaScope(raw_scope) if raw_scope else None
        scope_key = record.action_payload.get("scope_key")
        repository = get_provider_operations_store()
        affected_record_count = _apply_control_action(
            repository=repository,
            action_type=action_type,
            scope=scope,
            scope_key=scope_key,
        )
        event = ProviderOperationsEventRecord(
            event_id=f"provider_ops_evt_{uuid4().hex[:12]}",
            action_type=action_type,
            scope=scope,
            scope_key=scope_key,
            reason=str(record.action_payload.get("reason")),
            requested_by=(f"{record.requester_caller_app} (credential {record.requester_key_id})"),
            approved_by=f"{caller.caller_app} (credential {caller.credential_key_id})",
            affected_record_count=affected_record_count,
            authorization=authorization,
            recorded_at=_utcnow(),
        )
        repository.save_operations_event(event)
        outcome["event"] = event

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=_reset_target(
            action_type=request.action_type, scope=request.scope, scope_key=request.scope_key
        ),
        expected_hash=request.action_hash,
        current_payload_builder=lambda record: _reset_payload(
            action_type=ProviderOperationsControlActionType(
                str(record.action_payload.get("action_type"))
            ),
            scope=(
                ProviderQuotaScope(str(record.action_payload.get("scope")))
                if record.action_payload.get("scope")
                else None
            ),
            scope_key=record.action_payload.get("scope_key"),
            reason=str(record.action_payload.get("reason")),
        ),
        attribution=request.approved_by,
        execute=_execute_reset,
    )
    event = cast(ProviderOperationsEventRecord, outcome["event"])
    return ProviderOperationsResetApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        event=_to_event_descriptor(event),
        governed_action=executed,
        summary=[
            f"Applied provider-operations reset `{event.action_type.value}` under governed "
            f"action `{executed.action_id}`.",
            f"Affected provider-operations record count: {event.affected_record_count}.",
            f"Requested under credential `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}`.",
        ],
    )


def _reset_target(
    *,
    action_type: ProviderOperationsControlActionType,
    scope: ProviderQuotaScope | None,
    scope_key: str | None,
) -> str:
    """One pending action per exact reset shape.

    A pending targeted quota reset must not be superseded by an unrelated
    budget reset, so the target carries the full shape.
    """

    if scope is not None and scope_key is not None:
        return f"{action_type.value}:{scope.value}:{scope_key}"
    return action_type.value


def _reset_payload(
    *,
    action_type: ProviderOperationsControlActionType,
    scope: ProviderQuotaScope | None,
    scope_key: object,
    reason: str,
) -> dict[str, str | None]:
    return {
        "action_type": action_type.value,
        "scope": scope.value if scope is not None else None,
        "scope_key": str(scope_key) if scope_key is not None else None,
        "reason": reason,
    }


def _require_durable_reset_plane() -> None:
    if not _reset_actions_supported():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Provider-operations reset actions require LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE=sqlalchemy "
                "so the control-plane event history remains durable and reviewable."
            ),
        )


def _apply_control_action(
    *,
    repository: ProviderOperationsRepository,
    action_type: ProviderOperationsControlActionType,
    scope: ProviderQuotaScope | None,
    scope_key: object,
) -> int:
    if action_type == ProviderOperationsControlActionType.RESET_ALL_QUOTAS:
        return repository.reset_quota_states()
    if action_type == ProviderOperationsControlActionType.RESET_QUOTA_SCOPE:
        return repository.reset_quota_states(scope=scope, scope_key=str(scope_key))
    if action_type == ProviderOperationsControlActionType.RESET_BUDGET:
        return repository.reset_budget_state(budget_key=_BUDGET_KEY)
    if action_type == ProviderOperationsControlActionType.RESET_DEGRADATION:
        # Degradation state is keyed per provider identity (issue #176, S3);
        # the operator reset clears every candidate's counters.
        return repository.reset_degradation_states()
    if action_type == ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS:
        return (
            repository.reset_quota_states()
            + repository.reset_budget_state(budget_key=_BUDGET_KEY)
            + repository.reset_degradation_states()
        )
    raise RuntimeError("Unsupported provider-operations control action.")


def _validate_reset_shape(
    *,
    action_type: ProviderOperationsControlActionType,
    scope: ProviderQuotaScope | None,
    scope_key: str | None,
) -> None:
    if action_type == ProviderOperationsControlActionType.RESET_QUOTA_SCOPE:
        if scope is None or scope_key is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "RESET_QUOTA_SCOPE requires both `scope` and `scope_key` so the targeted quota reset remains explicit."
                ),
            )
        return

    if scope is not None or scope_key is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{action_type.value} does not accept `scope` or `scope_key`; use RESET_QUOTA_SCOPE for targeted quota resets."
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
