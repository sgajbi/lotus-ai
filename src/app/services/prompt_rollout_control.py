from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType, AuthorizationDecision
from app.contracts.prompts import (
    PromptControlActionRequest,
    PromptControlActionResponse,
    PromptControlActionType,
    PromptControlEventDescriptor,
    PromptControlHistoryResponse,
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptRolloutDescriptor,
    PromptRolloutSelectionMode,
)
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.eval_approval_gate_summary import build_prompt_approval_gate_summary
from app.services.prompt_rollout_models import PromptRolloutEventRecord, PromptRolloutStateRecord
from app.services.prompt_store import get_prompt_repository


def build_prompt_control_history(
    *, task_id: str | None = None, limit: int = 20
) -> PromptControlHistoryResponse:
    repository = get_prompt_repository()
    return PromptControlHistoryResponse(
        service=settings.service_name,
        version=settings.service_version,
        prompt_store_mode=settings.prompt_store_mode,
        supported_action_types=list(PromptControlActionType),
        latest_events=[
            _map_control_event(event)
            for event in repository.list_prompt_rollout_events(task_id=task_id, limit=limit)
        ],
        notes=[
            "Prompt promotion and rollback are explicit control-plane actions with requested-by, approved-by, and reason metadata.",
            "Prompt control history is returned newest-first and bounded by the route limit.",
            "Prompt bodies remain repository-managed; the live action surface only switches between durable prompt versions already known to the platform.",
            (
                "Prompt control history survives restart because the SQL-backed prompt store is active."
                if settings.prompt_store_mode == "sqlalchemy"
                else "Prompt control history is currently process-local because the in-memory prompt store is active."
            ),
        ],
    )


def apply_prompt_control_action(request: PromptControlActionRequest) -> PromptControlActionResponse:
    authorization = require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.PROMPT_CONTROL,
            task_id=request.task_id,
        )
    )
    _require_durable_prompt_control_plane(request.action_type)
    repository = get_prompt_repository()
    rollout_state = repository.get_prompt_rollout_state(request.task_id)
    if rollout_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt rollout state for task_id '{request.task_id}' was not found.",
        )

    updated_state, updated_prompts, event = _resolve_transition(
        rollout_state=rollout_state,
        request=request,
        authorization=authorization,
    )
    repository.save_prompt_rollout_transition(
        rollout_state=updated_state,
        updated_prompts=updated_prompts,
        event=event,
    )

    return PromptControlActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        event=_map_control_event(event),
        rollout_state=_map_rollout_state(updated_state, latest_control_event=event),
        summary=[
            f"Applied prompt action `{request.action_type.value}` for task `{request.task_id}`.",
            f"Active prompt is now `{updated_state.active_prompt_version}`.",
            f"Action requested by `{request.requested_by}` and approved by `{request.approved_by}`.",
        ],
    )


def _require_durable_prompt_control_plane(action_type: PromptControlActionType) -> None:
    if settings.prompt_store_mode != "sqlalchemy":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Prompt control actions require SQL-backed prompt rollout state so promote and "
                "rollback history remain durable across restart."
            ),
        )
    if (
        action_type == PromptControlActionType.PROMOTE_CANDIDATE
        and settings.evaluation_runtime_store_mode != "sqlalchemy"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Prompt promotion requires SQL-backed evaluation runtime evidence so the approval "
                "gate remains durable across restart."
            ),
        )


def _resolve_transition(
    *,
    rollout_state: PromptRolloutStateRecord,
    request: PromptControlActionRequest,
    authorization: AuthorizationDecision,
) -> tuple[PromptRolloutStateRecord, list[PromptDescriptor], PromptRolloutEventRecord]:
    if request.action_type == PromptControlActionType.PROMOTE_CANDIDATE:
        return _build_promote_transition(
            rollout_state=rollout_state,
            request=request,
            authorization=authorization,
        )
    if request.action_type == PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE:
        return _build_rollback_transition(
            rollout_state=rollout_state,
            request=request,
            authorization=authorization,
        )
    raise RuntimeError("Unsupported prompt control action.")


def _build_promote_transition(
    *,
    rollout_state: PromptRolloutStateRecord,
    request: PromptControlActionRequest,
    authorization: AuthorizationDecision,
) -> tuple[PromptRolloutStateRecord, list[PromptDescriptor], PromptRolloutEventRecord]:
    approval_gate = build_prompt_approval_gate_summary()
    if not approval_gate.approval_ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Prompt promotion is blocked until runtime-backed prompt approval evidence reaches "
                f"RUNTIME_PASS. Current approval state: {approval_gate.evidence_state.value}."
            ),
        )
    if request.candidate_prompt_version is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="candidate_prompt_version is required for PROMOTE_CANDIDATE.",
        )

    if request.candidate_prompt_version == rollout_state.active_prompt_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate prompt version already matches the active prompt version.",
        )

    repository = get_prompt_repository()
    candidate_prompt = repository.get_prompt_version(
        request.task_id,
        request.candidate_prompt_version,
    )
    if candidate_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Candidate prompt version '{request.candidate_prompt_version}' was not found "
                f"for task_id '{request.task_id}'."
            ),
        )
    if candidate_prompt.lifecycle_status != PromptLifecycleStatus.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Prompt version '{request.candidate_prompt_version}' is not a governed candidate "
                "and cannot be promoted."
            ),
        )

    active_prompt = _get_required_prompt_version(
        task_id=request.task_id,
        prompt_version=rollout_state.active_prompt_version,
    )

    updated_state = PromptRolloutStateRecord(
        task_id=rollout_state.task_id,
        active_prompt_version=candidate_prompt.prompt_version,
        candidate_prompt_version=None,
        previous_active_prompt_version=active_prompt.prompt_version,
        rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
        runtime_mutation_enabled=True,
    )
    updated_prompts = [
        active_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.RETIRED}),
        candidate_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.ACTIVE}),
    ]
    event = PromptRolloutEventRecord(
        event_id=f"prompt_evt_{uuid4().hex[:12]}",
        task_id=request.task_id,
        action_type=request.action_type,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        reason=request.reason,
        prior_active_prompt_version=active_prompt.prompt_version,
        resulting_active_prompt_version=candidate_prompt.prompt_version,
        prior_candidate_prompt_version=rollout_state.candidate_prompt_version,
        resulting_candidate_prompt_version=None,
        authorization=authorization,
        recorded_at=_utcnow(),
    )
    return updated_state, updated_prompts, event


def _build_rollback_transition(
    *,
    rollout_state: PromptRolloutStateRecord,
    request: PromptControlActionRequest,
    authorization: AuthorizationDecision,
) -> tuple[PromptRolloutStateRecord, list[PromptDescriptor], PromptRolloutEventRecord]:
    if request.candidate_prompt_version is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="candidate_prompt_version must be omitted for ROLLBACK_TO_PREVIOUS_ACTIVE.",
        )
    if rollout_state.previous_active_prompt_version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Prompt rollout state for task_id '{request.task_id}' has no prior active prompt "
                "available for rollback."
            ),
        )

    active_prompt = _get_required_prompt_version(
        task_id=request.task_id,
        prompt_version=rollout_state.active_prompt_version,
    )
    previous_active_prompt = _get_required_prompt_version(
        task_id=request.task_id,
        prompt_version=rollout_state.previous_active_prompt_version,
    )

    updated_state = PromptRolloutStateRecord(
        task_id=rollout_state.task_id,
        active_prompt_version=previous_active_prompt.prompt_version,
        candidate_prompt_version=active_prompt.prompt_version,
        previous_active_prompt_version=None,
        rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
        runtime_mutation_enabled=True,
    )
    updated_prompts = [
        active_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.CANDIDATE}),
        previous_active_prompt.model_copy(
            update={"lifecycle_status": PromptLifecycleStatus.ACTIVE}
        ),
    ]
    event = PromptRolloutEventRecord(
        event_id=f"prompt_evt_{uuid4().hex[:12]}",
        task_id=request.task_id,
        action_type=request.action_type,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        reason=request.reason,
        prior_active_prompt_version=active_prompt.prompt_version,
        resulting_active_prompt_version=previous_active_prompt.prompt_version,
        prior_candidate_prompt_version=rollout_state.candidate_prompt_version,
        resulting_candidate_prompt_version=active_prompt.prompt_version,
        authorization=authorization,
        recorded_at=_utcnow(),
    )
    return updated_state, updated_prompts, event


def _get_required_prompt_version(*, task_id: str, prompt_version: str) -> PromptDescriptor:
    prompt = get_prompt_repository().get_prompt_version(task_id, prompt_version)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Prompt rollout state for task_id '{task_id}' references missing prompt version "
                f"'{prompt_version}'."
            ),
        )
    return prompt


def _map_control_event(event: PromptRolloutEventRecord) -> PromptControlEventDescriptor:
    return PromptControlEventDescriptor(
        event_id=event.event_id,
        task_id=event.task_id,
        action_type=event.action_type,
        requested_by=event.requested_by,
        approved_by=event.approved_by,
        reason=event.reason,
        prior_active_prompt_version=event.prior_active_prompt_version,
        resulting_active_prompt_version=event.resulting_active_prompt_version,
        prior_candidate_prompt_version=event.prior_candidate_prompt_version,
        resulting_candidate_prompt_version=event.resulting_candidate_prompt_version,
        authorization=event.authorization,
        recorded_at=event.recorded_at,
    )


def _map_rollout_state(
    state: PromptRolloutStateRecord,
    *,
    latest_control_event: PromptRolloutEventRecord | None = None,
) -> PromptRolloutDescriptor:
    return PromptRolloutDescriptor(
        task_id=state.task_id,
        active_prompt_version=state.active_prompt_version,
        candidate_prompt_version=state.candidate_prompt_version,
        previous_active_prompt_version=state.previous_active_prompt_version,
        rollout_mode=state.rollout_mode,
        runtime_mutation_enabled=state.runtime_mutation_enabled,
        selection_reason=(
            "Prompt rollout state is now updated only through explicit governed promote and rollback actions."
        ),
        latest_control_event=(
            _map_control_event(latest_control_event) if latest_control_event is not None else None
        ),
    )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
