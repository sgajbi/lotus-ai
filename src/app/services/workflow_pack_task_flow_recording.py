from __future__ import annotations

from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDescriptor,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowCheckpointTransition,
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowStatus,
    WorkflowPackTaskFlowStepDescriptor,
    WorkflowPackTaskFlowStepStatus,
)
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.task_execution_models import TaskExecutionContext
from app.services.workflow_pack_task_flow_service import (
    create_task_flow,
    record_task_flow_checkpoint,
)

TASK_FLOW_EXECUTION_STEP_ID = "execute_workflow_pack"


def record_task_flow_for_workflow_pack_run(
    *,
    context: TaskExecutionContext,
    registration: WorkflowPackRegistrationDescriptor,
    workflow_surface: str | None,
    workflow_pack_run: WorkflowPackRunDescriptor,
) -> WorkflowPackTaskFlowDescriptor:
    task_flow_id = build_workflow_pack_task_flow_id(
        pack_family=registration.pack_family,
        request_id=workflow_pack_run.request_id,
    )
    created_at = workflow_pack_run.created_at
    initial_flow = _build_initial_task_flow(
        task_flow_id=task_flow_id,
        context=context,
        registration=registration,
        workflow_surface=workflow_surface,
        workflow_pack_run=workflow_pack_run,
        created_at=created_at,
    )
    create_task_flow(initial_flow)

    final_status = _resolve_task_flow_status(workflow_pack_run)
    checkpoint = _build_checkpoint(
        task_flow_id=task_flow_id,
        workflow_pack_run=workflow_pack_run,
        recorded_at=workflow_pack_run.last_updated_at,
    )
    return record_task_flow_checkpoint(
        task_flow_id=task_flow_id,
        checkpoint=checkpoint,
        resulting_status=final_status,
        current_step_id=(
            TASK_FLOW_EXECUTION_STEP_ID
            if final_status
            in {
                WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT,
                WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
                WorkflowPackTaskFlowStatus.BLOCKED,
                WorkflowPackTaskFlowStatus.RUNNING,
            }
            else None
        ),
        updated_at=workflow_pack_run.last_updated_at,
    )


def build_workflow_pack_task_flow_id(*, pack_family: str, request_id: str) -> str:
    return f"taskflow_{pack_family}_{request_id}"


def _build_initial_task_flow(
    *,
    task_flow_id: str,
    context: TaskExecutionContext,
    registration: WorkflowPackRegistrationDescriptor,
    workflow_surface: str | None,
    workflow_pack_run: WorkflowPackRunDescriptor,
    created_at: str,
) -> WorkflowPackTaskFlowDescriptor:
    evidence = _task_flow_evidence(
        evidence_type="workflow_pack_task_flow_recording",
        summary="Workflow-pack task-flow recording was initialized from a recorded pack run.",
        workflow_pack_run=workflow_pack_run,
    )
    return WorkflowPackTaskFlowDescriptor(
        task_flow_id=task_flow_id,
        workflow_pack_id=registration.pack_id,
        workflow_pack_version=registration.version,
        tenant_id=context.request.caller.tenant_id,
        caller=context.request.caller.caller_app,
        workflow_surface=workflow_surface,
        workflow_authority_owner=registration.workflow_authority_owner,
        flow_status=WorkflowPackTaskFlowStatus.RUNNING,
        current_step_id=TASK_FLOW_EXECUTION_STEP_ID,
        step_statuses=[
            WorkflowPackTaskFlowStepDescriptor(
                step_id=TASK_FLOW_EXECUTION_STEP_ID,
                name="Execute workflow pack",
                status=WorkflowPackTaskFlowStepStatus.RUNNING,
                run_refs=[workflow_pack_run.run_id],
            )
        ],
        run_refs=[workflow_pack_run.run_id],
        runtime_states={workflow_pack_run.run_id: workflow_pack_run.runtime_state},
        review_states={workflow_pack_run.run_id: workflow_pack_run.review_state},
        supportability_status=workflow_pack_run.supportability_status,
        created_at=created_at,
        updated_at=created_at,
        authorization_evidence_ref=evidence,
        readiness_evidence_ref=evidence,
    )


def _build_checkpoint(
    *,
    task_flow_id: str,
    workflow_pack_run: WorkflowPackRunDescriptor,
    recorded_at: str,
) -> WorkflowPackTaskFlowCheckpointDescriptor:
    final_status = _resolve_task_flow_status(workflow_pack_run)
    return WorkflowPackTaskFlowCheckpointDescriptor(
        checkpoint_id=f"{task_flow_id}_checkpoint_{workflow_pack_run.request_id}",
        task_flow_id=task_flow_id,
        step_id=TASK_FLOW_EXECUTION_STEP_ID,
        transition=_resolve_checkpoint_transition(final_status),
        actor="lotus-ai",
        recorded_at=recorded_at,
        evidence_refs=[
            _task_flow_evidence(
                evidence_type="workflow_pack_run_recorded",
                summary="Workflow-pack run ledger state was linked into the task-flow checkpoint.",
                workflow_pack_run=workflow_pack_run,
            )
        ],
        run_id=workflow_pack_run.run_id,
        review_ref=workflow_pack_run.run_id,
        reason="Workflow-pack execution produced a task-flow checkpoint.",
        degraded=workflow_pack_run.runtime_state == WorkflowPackRunRuntimeState.FAILED,
        unsupported=False,
    )


def _resolve_task_flow_status(
    workflow_pack_run: WorkflowPackRunDescriptor,
) -> WorkflowPackTaskFlowStatus:
    if workflow_pack_run.runtime_state == WorkflowPackRunRuntimeState.FAILED:
        return WorkflowPackTaskFlowStatus.FAILED
    if workflow_pack_run.review_state == WorkflowPackRunReviewState.AWAITING_REVIEW:
        return WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW
    if workflow_pack_run.runtime_state == WorkflowPackRunRuntimeState.SUPERSEDED:
        return WorkflowPackTaskFlowStatus.SUPERSEDED
    return WorkflowPackTaskFlowStatus.COMPLETED


def _resolve_checkpoint_transition(
    final_status: WorkflowPackTaskFlowStatus,
) -> WorkflowPackTaskFlowCheckpointTransition:
    if final_status == WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW:
        return WorkflowPackTaskFlowCheckpointTransition.REVIEW_REQUESTED
    if final_status == WorkflowPackTaskFlowStatus.FAILED:
        return WorkflowPackTaskFlowCheckpointTransition.STEP_FAILED
    if final_status == WorkflowPackTaskFlowStatus.SUPERSEDED:
        return WorkflowPackTaskFlowCheckpointTransition.FLOW_SUPERSEDED
    return WorkflowPackTaskFlowCheckpointTransition.FLOW_COMPLETED


def _task_flow_evidence(
    *,
    evidence_type: str,
    summary: str,
    workflow_pack_run: WorkflowPackRunDescriptor,
) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type=evidence_type,
        summary=summary,
        attributes={
            "workflow_pack_run_id": workflow_pack_run.run_id,
            "registration_ref": workflow_pack_run.registration_ref,
            "runtime_state": workflow_pack_run.runtime_state.value,
            "review_state": workflow_pack_run.review_state.value,
        },
    )
