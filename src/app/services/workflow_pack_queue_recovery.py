from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDetailResponse,
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueuePolicyDescriptor,
    WorkflowPackQueueRecoveryActionType,
    WorkflowPackQueueState,
)
from app.services.workflow_pack_queue_events import (
    build_workflow_pack_queue_event_detail,
    record_workflow_pack_queue_event,
)
from app.services.workflow_pack_queue_policy_catalog import (
    get_workflow_pack_queue_policy_descriptor,
)

RETRY_BLOCKED_REASON_CODE = "QUEUE_RETRY_BLOCKED_BY_POLICY"
REPLAY_BLOCKED_REASON_CODE = "QUEUE_REPLAY_BLOCKED_BY_POLICY"


def record_workflow_pack_queue_retry_decision(
    *,
    queue_item_id: str,
    failure_code: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> WorkflowPackQueueEventDescriptor:
    _require_recovery_evidence(requested_by=requested_by, reason=reason, evidence_ref=evidence_ref)
    history = _load_history(queue_item_id).events
    terminal_event = _latest_terminal_event(history)
    policy = _resolve_policy(terminal_event)
    prior_retry_count = _count_recovery_events(
        history=history,
        event_type=WorkflowPackQueueEventType.RETRY_RECORDED,
    )
    attempt_number = prior_retry_count + 1
    retry_allowed = (
        terminal_event.state
        in {
            WorkflowPackQueueState.REJECTED,
            WorkflowPackQueueState.TIMED_OUT,
            WorkflowPackQueueState.DEGRADED,
        }
        and failure_code in set(policy.retry_policy.retryable_failure_codes)
        and attempt_number < policy.retry_policy.max_attempts
    )
    if not retry_allowed:
        return _record_recovery_event(
            source_event=terminal_event,
            event_type=WorkflowPackQueueEventType.RETRY_BLOCKED,
            recovery_action_type=WorkflowPackQueueRecoveryActionType.RETRY,
            state=terminal_event.state,
            reason_code=RETRY_BLOCKED_REASON_CODE,
            recovery_attempt_number=attempt_number,
            requested_by=requested_by,
            evidence_ref=evidence_ref,
            message=(
                "Workflow-pack queue retry blocked by policy for "
                f"`{terminal_event.workflow_pack_id}@{terminal_event.workflow_pack_version}` "
                f"after failure code `{failure_code}`: {reason}"
            ),
        )
    return _record_recovery_event(
        source_event=terminal_event,
        event_type=WorkflowPackQueueEventType.RETRY_RECORDED,
        recovery_action_type=WorkflowPackQueueRecoveryActionType.RETRY,
        state=WorkflowPackQueueState.QUEUED,
        reason_code=failure_code,
        recovery_attempt_number=attempt_number,
        requested_by=requested_by,
        evidence_ref=evidence_ref,
        message=(
            "Workflow-pack queue retry recorded as governed evidence for "
            f"`{terminal_event.workflow_pack_id}@{terminal_event.workflow_pack_version}` "
            f"after failure code `{failure_code}`: {reason}"
        ),
    )


def record_workflow_pack_queue_replay_decision(
    *,
    queue_item_id: str,
    requested_by: str,
    reason: str,
    evidence_ref: str,
) -> WorkflowPackQueueEventDescriptor:
    _require_recovery_evidence(requested_by=requested_by, reason=reason, evidence_ref=evidence_ref)
    history = _load_history(queue_item_id).events
    terminal_event = _latest_terminal_event(history)
    _resolve_policy(terminal_event)
    prior_replay_count = _count_recovery_events(
        history=history,
        event_type=WorkflowPackQueueEventType.REPLAY_RECORDED,
    )
    attempt_number = prior_replay_count + 1
    if prior_replay_count >= 1:
        return _record_recovery_event(
            source_event=terminal_event,
            event_type=WorkflowPackQueueEventType.REPLAY_BLOCKED,
            recovery_action_type=WorkflowPackQueueRecoveryActionType.REPLAY,
            state=terminal_event.state,
            reason_code=REPLAY_BLOCKED_REASON_CODE,
            recovery_attempt_number=attempt_number,
            requested_by=requested_by,
            evidence_ref=evidence_ref,
            message=(
                "Workflow-pack queue replay blocked because a replay decision already exists for "
                f"`{terminal_event.workflow_pack_id}@{terminal_event.workflow_pack_version}`: {reason}"
            ),
        )
    return _record_recovery_event(
        source_event=terminal_event,
        event_type=WorkflowPackQueueEventType.REPLAY_RECORDED,
        recovery_action_type=WorkflowPackQueueRecoveryActionType.REPLAY,
        state=WorkflowPackQueueState.QUEUED,
        reason_code="QUEUE_REPLAY_RECORDED",
        recovery_attempt_number=attempt_number,
        requested_by=requested_by,
        evidence_ref=evidence_ref,
        message=(
            "Workflow-pack queue replay recorded as governed evidence for "
            f"`{terminal_event.workflow_pack_id}@{terminal_event.workflow_pack_version}`: {reason}"
        ),
    )


def _require_recovery_evidence(*, requested_by: str, reason: str, evidence_ref: str) -> None:
    if not requested_by.strip() or not reason.strip() or not evidence_ref.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Workflow-pack queue recovery requires non-empty requested_by, reason, and "
                "evidence_ref."
            ),
        )


def _load_history(queue_item_id: str) -> WorkflowPackQueueEventDetailResponse:
    try:
        return build_workflow_pack_queue_event_detail(queue_item_id=queue_item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _latest_terminal_event(
    history: list[WorkflowPackQueueEventDescriptor],
) -> WorkflowPackQueueEventDescriptor:
    for event in reversed(history):
        if event.state in {
            WorkflowPackQueueState.REJECTED,
            WorkflowPackQueueState.CANCELLED,
            WorkflowPackQueueState.TIMED_OUT,
            WorkflowPackQueueState.DEGRADED,
            WorkflowPackQueueState.COMPLETED_HANDOFF,
        }:
            return event
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Workflow-pack queue recovery requires a terminal queue event.",
    )


def _resolve_policy(event: WorkflowPackQueueEventDescriptor) -> WorkflowPackQueuePolicyDescriptor:
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id=event.workflow_pack_id,
        version=event.workflow_pack_version,
    )
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue recovery requires a declared queue policy for "
                f"`{event.workflow_pack_id}@{event.workflow_pack_version}`."
            ),
        )
    return policy


def _count_recovery_events(
    *,
    history: list[WorkflowPackQueueEventDescriptor],
    event_type: WorkflowPackQueueEventType,
) -> int:
    return sum(1 for event in history if event.event_type is event_type)


def _record_recovery_event(
    *,
    source_event: WorkflowPackQueueEventDescriptor,
    event_type: WorkflowPackQueueEventType,
    recovery_action_type: WorkflowPackQueueRecoveryActionType,
    state: WorkflowPackQueueState,
    reason_code: str,
    recovery_attempt_number: int,
    requested_by: str,
    evidence_ref: str,
    message: str,
) -> WorkflowPackQueueEventDescriptor:
    return record_workflow_pack_queue_event(
        queue_item_id=source_event.queue_item_id,
        event_type=event_type,
        workflow_pack_id=source_event.workflow_pack_id,
        workflow_pack_version=source_event.workflow_pack_version,
        state=state,
        message=message,
        policy_id=source_event.policy_id,
        lane=source_event.lane,
        caller_app=source_event.caller_app,
        correlation_id=source_event.correlation_id,
        tenant_id=source_event.tenant_id,
        workflow_surface=source_event.workflow_surface,
        reason_code=reason_code,
        source_queue_item_id=source_event.queue_item_id,
        recovery_action_type=recovery_action_type,
        recovery_attempt_number=recovery_attempt_number,
        requested_by=requested_by,
        evidence_ref=evidence_ref,
    )
