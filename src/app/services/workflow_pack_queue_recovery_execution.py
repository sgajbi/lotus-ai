from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
)
from app.contracts.workflow_pack_queue_recovery import (
    WorkflowPackQueueRecoveryExecutionResponse,
)
from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.services.workflow_pack_execution import execute_workflow_pack
from app.services.workflow_pack_queue_recovery import (
    get_workflow_pack_queue_recovery_source_event,
    record_workflow_pack_queue_replay_decision,
    record_workflow_pack_queue_retry_decision,
)
from app.services.workflow_pack_queue_request_snapshots import (
    build_workflow_pack_execution_request_from_queue_snapshot,
)


def execute_workflow_pack_queue_retry(
    *,
    queue_item_id: str,
    failure_code: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    execution_request = _build_execution_request(
        source_event=get_workflow_pack_queue_recovery_source_event(queue_item_id=queue_item_id)
    )
    event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
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
    execution = execute_workflow_pack(execution_request)
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
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> WorkflowPackQueueRecoveryExecutionResponse:
    execution_request = _build_execution_request(
        source_event=get_workflow_pack_queue_recovery_source_event(queue_item_id=queue_item_id)
    )
    event = record_workflow_pack_queue_replay_decision(
        queue_item_id=queue_item_id,
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
    execution = execute_workflow_pack(execution_request)
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
