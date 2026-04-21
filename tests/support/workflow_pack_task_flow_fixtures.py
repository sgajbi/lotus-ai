from __future__ import annotations

from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowCheckpointTransition,
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowStatus,
    WorkflowPackTaskFlowStepDescriptor,
    WorkflowPackTaskFlowStepStatus,
)


def workflow_pack_task_flow_evidence(summary: str) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="unit_test_evidence",
        summary=summary,
        attributes={"source": "workflow_pack_task_flow_fixture"},
    )


def workflow_pack_task_flow_descriptor(
    *,
    task_flow_id: str = "task-flow-001",
    flow_status: WorkflowPackTaskFlowStatus = WorkflowPackTaskFlowStatus.CREATED,
    current_step_id: str | None = None,
    updated_at: str = "2026-04-21T01:00:00Z",
) -> WorkflowPackTaskFlowDescriptor:
    return WorkflowPackTaskFlowDescriptor(
        task_flow_id=task_flow_id,
        workflow_pack_id="advisor_brief.pack",
        workflow_pack_version="v1",
        tenant_id="tenant-sg-001",
        caller="lotus-gateway",
        workflow_surface="advisor-brief-panel",
        workflow_authority_owner="lotus-advise",
        flow_status=flow_status,
        current_step_id=current_step_id,
        step_statuses=[
            WorkflowPackTaskFlowStepDescriptor(
                step_id="draft-brief",
                name="Draft advisor brief",
                status=WorkflowPackTaskFlowStepStatus.PENDING,
            )
        ],
        run_refs=["run-001"],
        runtime_states={"run-001": WorkflowPackRunRuntimeState.STAGED},
        review_states={"run-001": WorkflowPackRunReviewState.AWAITING_REVIEW},
        supportability_status=WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        created_at="2026-04-21T01:00:00Z",
        updated_at=updated_at,
        authorization_evidence_ref=workflow_pack_task_flow_evidence("caller authorized"),
        readiness_evidence_ref=workflow_pack_task_flow_evidence("stores ready"),
    )


def workflow_pack_task_flow_checkpoint(
    *,
    checkpoint_id: str = "checkpoint-001",
    task_flow_id: str = "task-flow-001",
    recorded_at: str = "2026-04-21T01:01:00Z",
) -> WorkflowPackTaskFlowCheckpointDescriptor:
    return WorkflowPackTaskFlowCheckpointDescriptor(
        checkpoint_id=checkpoint_id,
        task_flow_id=task_flow_id,
        step_id="draft-brief",
        transition=WorkflowPackTaskFlowCheckpointTransition.STEP_STARTED,
        actor="lotus-ai",
        recorded_at=recorded_at,
        evidence_refs=[workflow_pack_task_flow_evidence("step started")],
        run_id="run-001",
        reason="Advisor brief drafting started.",
    )
