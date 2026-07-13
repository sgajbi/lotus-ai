from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
)
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunRecoveryActionType,
    WorkflowPackRunRecoveryLineageDescriptor,
)
from app.contracts.workflow_pack_queue_recovery import (
    WorkflowPackQueueRecoveryExecutionResponse,
)
from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.http.authenticated_caller import bind_internal_authenticated_caller
from app.services.workflow_pack_execution import execute_workflow_pack
from app.services.workflow_pack_queue_recovery import (
    authorize_workflow_pack_queue_recovery_caller,
    get_workflow_pack_queue_recovery_source_event,
    record_workflow_pack_queue_replay_decision,
    record_workflow_pack_queue_retry_decision,
)
from app.services.workflow_pack_queue_request_snapshots import (
    build_workflow_pack_execution_request_from_queue_snapshot,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store


def execute_workflow_pack_queue_retry(
    *,
    queue_item_id: str,
    caller_app: str,
    failure_code: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    authorize_workflow_pack_queue_recovery_caller(caller_app=caller_app)
    source_event = get_workflow_pack_queue_recovery_source_event(queue_item_id=queue_item_id)
    execution_request = _build_execution_request(source_event=source_event)
    event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
        caller_app=caller_app,
        failure_code=failure_code,
        requested_by=requested_by,
        reason=reason,
        evidence_ref=evidence_ref,
    )
    if event.event_type is not WorkflowPackQueueEventType.RETRY_RECORDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue retry execution was not started because retry was blocked "
                f"by policy. Blocking event: {event.event_id}."
            ),
        )
    with bind_internal_authenticated_caller(
        caller_app=execution_request.task_request.caller.caller_app,
        trust_source="retained_queue_request_snapshot",
    ):
        execution = execute_workflow_pack(
            execution_request,
            recovery_lineage=_build_recovery_lineage(
                source_event=source_event,
                decision_event=event,
                action_type=WorkflowPackRunRecoveryActionType.RETRY,
            ),
        )
    return WorkflowPackQueueRecoveryExecutionResponse(
        service=execution.service,
        version=execution.version,
        phase=settings.delivery_phase,
        decision_event=event,
        execution=execution,
        status_summary=[
            "Workflow-pack queue retry decision was recorded and executed from the retained request snapshot.",
            "The retry execution used the normal workflow-pack execution path, including eligibility, queue admission, run ledger, and task-flow recording.",
        ],
    )


def execute_workflow_pack_queue_replay(
    *,
    queue_item_id: str,
    caller_app: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    authorize_workflow_pack_queue_recovery_caller(caller_app=caller_app)
    source_event = get_workflow_pack_queue_recovery_source_event(queue_item_id=queue_item_id)
    execution_request = _build_execution_request(source_event=source_event)
    event = record_workflow_pack_queue_replay_decision(
        queue_item_id=queue_item_id,
        caller_app=caller_app,
        requested_by=requested_by,
        reason=reason,
        evidence_ref=evidence_ref,
    )
    if event.event_type is not WorkflowPackQueueEventType.REPLAY_RECORDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue replay execution was not started because replay was blocked "
                f"by policy. Blocking event: {event.event_id}."
            ),
        )
    with bind_internal_authenticated_caller(
        caller_app=execution_request.task_request.caller.caller_app,
        trust_source="retained_queue_request_snapshot",
    ):
        execution = execute_workflow_pack(
            execution_request,
            recovery_lineage=_build_recovery_lineage(
                source_event=source_event,
                decision_event=event,
                action_type=WorkflowPackRunRecoveryActionType.REPLAY,
            ),
        )
    return WorkflowPackQueueRecoveryExecutionResponse(
        service=execution.service,
        version=execution.version,
        phase=settings.delivery_phase,
        decision_event=event,
        execution=execution,
        status_summary=[
            "Workflow-pack queue replay decision was recorded and executed from the retained request snapshot.",
            "The replay execution used the normal workflow-pack execution path, including eligibility, queue admission, run ledger, and task-flow recording.",
        ],
    )


def _build_execution_request(
    *, source_event: WorkflowPackQueueEventDescriptor
) -> WorkflowPackExecutionRequest:
    try:
        return build_workflow_pack_execution_request_from_queue_snapshot(source_event=source_event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _build_recovery_lineage(
    *,
    source_event: WorkflowPackQueueEventDescriptor,
    decision_event: WorkflowPackQueueEventDescriptor,
    action_type: WorkflowPackRunRecoveryActionType,
) -> WorkflowPackRunRecoveryLineageDescriptor:
    return WorkflowPackRunRecoveryLineageDescriptor(
        recovery_action_type=action_type,
        source_queue_item_id=source_event.queue_item_id,
        recovery_decision_event_id=decision_event.event_id,
        recovery_attempt_number=decision_event.recovery_attempt_number,
        source_workflow_pack_run_id=_resolve_source_workflow_pack_run_id(source_event),
        requested_by=decision_event.requested_by,
        evidence_ref=decision_event.evidence_ref,
    )


def _resolve_source_workflow_pack_run_id(
    source_event: WorkflowPackQueueEventDescriptor,
) -> str | None:
    if source_event.correlation_id is None:
        return None
    candidates = get_workflow_pack_run_store().query_runs(
        pack_id=source_event.workflow_pack_id,
        caller_app=source_event.caller_app,
        tenant_id=source_event.tenant_id,
        workflow_surface=source_event.workflow_surface,
        limit=20,
    )
    for candidate in candidates:
        if candidate.correlation_id == source_event.correlation_id:
            return candidate.run_id
    return None
