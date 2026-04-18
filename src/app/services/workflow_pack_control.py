from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackControlActionRequest,
    WorkflowPackControlActionResponse,
    WorkflowPackControlActionType,
    WorkflowPackControlEventDescriptor,
    WorkflowPackControlHistoryResponse,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationStatus,
)
from app.services.workflow_pack_registry import (
    append_workflow_pack_control_event,
    get_workflow_pack_registration,
    list_workflow_pack_control_events,
    save_workflow_pack_registration,
)

_OPERATOR_CALLER_APP = "lotus-platform"


def build_workflow_pack_control_history(
    *,
    pack_id: str | None = None,
    version: str | None = None,
    limit: int = 20,
) -> WorkflowPackControlHistoryResponse:
    return WorkflowPackControlHistoryResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        control_plane_store_mode="memory",
        supported_action_types=list(WorkflowPackControlActionType),
        latest_events=list_workflow_pack_control_events(
            pack_id=pack_id,
            version=version,
            limit=limit,
        ),
        notes=[
            "Workflow-pack pause, resume, deprecate, and retire actions are explicit control-plane events with operator reason and approval metadata.",
            "This slice is currently process-local and intended to prove transition semantics before durable workflow-pack control storage is introduced.",
            "Workflow-pack control actions do not edit workflow logic; they only change runtime registration and activation posture.",
        ],
    )


def apply_workflow_pack_control_action(
    request: WorkflowPackControlActionRequest,
) -> WorkflowPackControlActionResponse:
    _require_operator_caller(request.caller_app)
    registration = get_workflow_pack_registration(pack_id=request.pack_id, version=request.version)
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow-pack registration '{request.pack_id}@{request.version}' was not found.",
        )

    updated_registration = _apply_transition(registration=registration, request=request)
    event = WorkflowPackControlEventDescriptor(
        event_id=f"workflow_pack_evt_{uuid4().hex[:12]}",
        pack_id=registration.pack_id,
        version=registration.version,
        action_type=request.action_type,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        reason=request.reason,
        prior_registration_status=registration.registration_status,
        resulting_registration_status=updated_registration.registration_status,
        prior_activation_state=registration.activation_state,
        resulting_activation_state=updated_registration.activation_state,
        caller_app=request.caller_app,
        recorded_at=_utcnow(),
    )
    save_workflow_pack_registration(updated_registration)
    append_workflow_pack_control_event(event)
    return WorkflowPackControlActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        event=event,
        registration=updated_registration,
        summary=[
            f"Applied workflow-pack action `{request.action_type.value}` to `{registration.pack_id}@{registration.version}`.",
            f"Activation state moved from `{registration.activation_state.value}` to `{updated_registration.activation_state.value}`.",
            f"Action requested by `{request.requested_by}` and approved by `{request.approved_by}`.",
        ],
    )


def _apply_transition(
    *,
    registration: WorkflowPackRegistrationDescriptor,
    request: WorkflowPackControlActionRequest,
) -> WorkflowPackRegistrationDescriptor:
    if request.action_type == WorkflowPackControlActionType.PAUSE:
        return _pause_registration(registration)
    if request.action_type == WorkflowPackControlActionType.RESUME:
        return _resume_registration(registration)
    if request.action_type == WorkflowPackControlActionType.DEPRECATE:
        return _deprecate_registration(registration)
    if request.action_type == WorkflowPackControlActionType.RETIRE:
        return _retire_registration(registration)
    raise RuntimeError("Unsupported workflow-pack control action.")


def _pause_registration(
    registration: WorkflowPackRegistrationDescriptor,
) -> WorkflowPackRegistrationDescriptor:
    if registration.activation_state in {
        WorkflowPackActivationState.PAUSED,
        WorkflowPackActivationState.RETIRED,
        WorkflowPackActivationState.DARK,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Workflow-pack registration '{registration.pack_id}@{registration.version}' "
                f"cannot be paused from activation state '{registration.activation_state.value}'."
            ),
        )
    return registration.model_copy(
        update={
            "activation_state": WorkflowPackActivationState.PAUSED,
            "pause_state": f"PAUSED_FROM_{registration.activation_state.value}",
            "last_changed_at": _utcnow(),
        }
    )


def _resume_registration(
    registration: WorkflowPackRegistrationDescriptor,
) -> WorkflowPackRegistrationDescriptor:
    if registration.activation_state != WorkflowPackActivationState.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Workflow-pack registration '{registration.pack_id}@{registration.version}' "
                "is not paused and cannot be resumed."
            ),
        )
    resume_state = _resolve_resume_state(registration)
    return registration.model_copy(
        update={
            "activation_state": resume_state,
            "pause_state": "NOT_PAUSED",
            "last_changed_at": _utcnow(),
        }
    )


def _deprecate_registration(
    registration: WorkflowPackRegistrationDescriptor,
) -> WorkflowPackRegistrationDescriptor:
    if registration.activation_state == WorkflowPackActivationState.RETIRED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Workflow-pack registration '{registration.pack_id}@{registration.version}' "
                "is already retired and cannot be deprecated."
            ),
        )
    return registration.model_copy(
        update={
            "activation_state": WorkflowPackActivationState.DEPRECATED,
            "pause_state": "NOT_PAUSED",
            "last_changed_at": _utcnow(),
        }
    )


def _retire_registration(
    registration: WorkflowPackRegistrationDescriptor,
) -> WorkflowPackRegistrationDescriptor:
    if registration.registration_status == WorkflowPackRegistrationStatus.RETIRED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Workflow-pack registration '{registration.pack_id}@{registration.version}' "
                "is already retired."
            ),
        )
    return registration.model_copy(
        update={
            "registration_status": WorkflowPackRegistrationStatus.RETIRED,
            "activation_state": WorkflowPackActivationState.RETIRED,
            "pause_state": "NOT_PAUSED",
            "last_changed_at": _utcnow(),
        }
    )


def _resolve_resume_state(
    registration: WorkflowPackRegistrationDescriptor,
) -> WorkflowPackActivationState:
    events = list_workflow_pack_control_events(
        pack_id=registration.pack_id,
        version=registration.version,
        limit=50,
    )
    for event in events:
        if event.action_type == WorkflowPackControlActionType.PAUSE:
            return event.prior_activation_state
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Workflow-pack registration '{registration.pack_id}@{registration.version}' has no "
            "recorded pause event to resume from."
        ),
    )


def _require_operator_caller(caller_app: str) -> None:
    if caller_app != _OPERATOR_CALLER_APP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Workflow-pack control actions are currently limited to the lotus-platform "
                "operator caller while the control plane remains process-local."
            ),
        )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
