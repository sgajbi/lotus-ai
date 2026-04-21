from __future__ import annotations

from app.contracts.workflow_pack_task_flows import WorkflowPackTaskFlowStatus


TASK_FLOW_TERMINAL_STATES = {
    WorkflowPackTaskFlowStatus.COMPLETED,
    WorkflowPackTaskFlowStatus.FAILED,
    WorkflowPackTaskFlowStatus.CANCELLED,
    WorkflowPackTaskFlowStatus.EXPIRED,
    WorkflowPackTaskFlowStatus.SUPERSEDED,
}

TASK_FLOW_ALLOWED_TRANSITIONS: dict[
    WorkflowPackTaskFlowStatus, set[WorkflowPackTaskFlowStatus]
] = {
    WorkflowPackTaskFlowStatus.CREATED: {
        WorkflowPackTaskFlowStatus.RUNNING,
        WorkflowPackTaskFlowStatus.CANCELLED,
        WorkflowPackTaskFlowStatus.EXPIRED,
    },
    WorkflowPackTaskFlowStatus.RUNNING: {
        WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT,
        WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        WorkflowPackTaskFlowStatus.BLOCKED,
        WorkflowPackTaskFlowStatus.COMPLETED,
        WorkflowPackTaskFlowStatus.FAILED,
        WorkflowPackTaskFlowStatus.CANCELLED,
        WorkflowPackTaskFlowStatus.EXPIRED,
        WorkflowPackTaskFlowStatus.SUPERSEDED,
    },
    WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT: {
        WorkflowPackTaskFlowStatus.RUNNING,
        WorkflowPackTaskFlowStatus.BLOCKED,
        WorkflowPackTaskFlowStatus.CANCELLED,
        WorkflowPackTaskFlowStatus.EXPIRED,
    },
    WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW: {
        WorkflowPackTaskFlowStatus.RUNNING,
        WorkflowPackTaskFlowStatus.BLOCKED,
        WorkflowPackTaskFlowStatus.COMPLETED,
        WorkflowPackTaskFlowStatus.CANCELLED,
        WorkflowPackTaskFlowStatus.EXPIRED,
        WorkflowPackTaskFlowStatus.SUPERSEDED,
    },
    WorkflowPackTaskFlowStatus.BLOCKED: {
        WorkflowPackTaskFlowStatus.RUNNING,
        WorkflowPackTaskFlowStatus.FAILED,
        WorkflowPackTaskFlowStatus.CANCELLED,
        WorkflowPackTaskFlowStatus.EXPIRED,
        WorkflowPackTaskFlowStatus.SUPERSEDED,
    },
    WorkflowPackTaskFlowStatus.COMPLETED: set(),
    WorkflowPackTaskFlowStatus.FAILED: set(),
    WorkflowPackTaskFlowStatus.CANCELLED: set(),
    WorkflowPackTaskFlowStatus.EXPIRED: set(),
    WorkflowPackTaskFlowStatus.SUPERSEDED: set(),
}


def is_task_flow_transition_allowed(
    current_status: WorkflowPackTaskFlowStatus,
    next_status: WorkflowPackTaskFlowStatus,
) -> bool:
    return next_status in TASK_FLOW_ALLOWED_TRANSITIONS[current_status]


def require_task_flow_transition_allowed(
    current_status: WorkflowPackTaskFlowStatus,
    next_status: WorkflowPackTaskFlowStatus,
) -> None:
    if is_task_flow_transition_allowed(current_status, next_status):
        return
    raise ValueError(
        f"Task-flow transition from {current_status.value} to {next_status.value} is not allowed."
    )

