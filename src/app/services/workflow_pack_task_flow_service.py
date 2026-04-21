from __future__ import annotations

from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowStatus,
    WorkflowPackTaskFlowStepDescriptor,
)
from app.repositories.workflow_pack_task_flow_repository import (
    WorkflowPackTaskFlowCheckpointRecord,
    WorkflowPackTaskFlowRecord,
    WorkflowPackTaskFlowRepository,
)
from app.services.runtime_readiness import get_workflow_pack_task_flow_store_runtime_status
from app.services.workflow_pack_task_flow_contracts import require_task_flow_transition_allowed
from app.services.workflow_pack_task_flow_store import get_workflow_pack_task_flow_store


class WorkflowPackTaskFlowStoreNotReadyError(RuntimeError):
    def __init__(self, message: str, *, status: RuntimeReadinessStatus) -> None:
        super().__init__(message)
        self.status = status


class WorkflowPackTaskFlowNotFoundError(LookupError):
    pass


def ensure_workflow_pack_task_flow_store_ready() -> None:
    status_descriptor = get_workflow_pack_task_flow_store_runtime_status()
    if status_descriptor.status != RuntimeReadinessStatus.READY:
        raise WorkflowPackTaskFlowStoreNotReadyError(
            f"Workflow-pack task-flow store is not ready: {status_descriptor.detail}",
            status=status_descriptor.status,
        )


def list_task_flows(
    *, store: WorkflowPackTaskFlowRepository | None = None
) -> list[WorkflowPackTaskFlowDescriptor]:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = store or get_workflow_pack_task_flow_store()
    return [record.descriptor for record in task_flow_store.list_task_flows()]


def get_task_flow(
    task_flow_id: str, *, store: WorkflowPackTaskFlowRepository | None = None
) -> WorkflowPackTaskFlowDescriptor | None:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = store or get_workflow_pack_task_flow_store()
    record = task_flow_store.get_task_flow(task_flow_id=task_flow_id)
    if record is None:
        return None
    return record.descriptor


def create_task_flow(
    descriptor: WorkflowPackTaskFlowDescriptor,
    *,
    store: WorkflowPackTaskFlowRepository | None = None,
) -> WorkflowPackTaskFlowDescriptor:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = store or get_workflow_pack_task_flow_store()
    task_flow_store.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=descriptor))
    return descriptor


def record_task_flow_checkpoint(
    *,
    task_flow_id: str,
    checkpoint: WorkflowPackTaskFlowCheckpointDescriptor,
    resulting_status: WorkflowPackTaskFlowStatus,
    current_step_id: str | None,
    updated_at: str,
    store: WorkflowPackTaskFlowRepository | None = None,
) -> WorkflowPackTaskFlowDescriptor:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = store or get_workflow_pack_task_flow_store()
    existing_record = task_flow_store.get_task_flow(task_flow_id=task_flow_id)
    if existing_record is None:
        raise WorkflowPackTaskFlowNotFoundError(f"Unknown workflow-pack task flow: {task_flow_id}")

    existing = existing_record.descriptor
    require_task_flow_transition_allowed(existing.flow_status, resulting_status)
    updated = _append_checkpoint_to_task_flow(
        existing,
        checkpoint=checkpoint,
        resulting_status=resulting_status,
        current_step_id=current_step_id,
        updated_at=updated_at,
    )
    task_flow_store.save_checkpoint(WorkflowPackTaskFlowCheckpointRecord(descriptor=checkpoint))
    task_flow_store.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=updated))
    return updated


def list_task_flow_checkpoints(
    task_flow_id: str, *, store: WorkflowPackTaskFlowRepository | None = None
) -> list[WorkflowPackTaskFlowCheckpointDescriptor]:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = store or get_workflow_pack_task_flow_store()
    return [
        record.descriptor for record in task_flow_store.list_checkpoints(task_flow_id=task_flow_id)
    ]


def _append_checkpoint_to_task_flow(
    descriptor: WorkflowPackTaskFlowDescriptor,
    *,
    checkpoint: WorkflowPackTaskFlowCheckpointDescriptor,
    resulting_status: WorkflowPackTaskFlowStatus,
    current_step_id: str | None,
    updated_at: str,
) -> WorkflowPackTaskFlowDescriptor:
    if checkpoint.task_flow_id != descriptor.task_flow_id:
        raise ValueError("checkpoint task_flow_id must match the target task flow")
    if checkpoint.step_id not in {step.step_id for step in descriptor.step_statuses}:
        raise ValueError("checkpoint step_id must reference a declared task-flow step")

    checkpoint_refs = [*descriptor.checkpoint_refs]
    if checkpoint.checkpoint_id not in checkpoint_refs:
        checkpoint_refs.append(checkpoint.checkpoint_id)

    step_statuses = [
        _append_checkpoint_to_step(step, checkpoint)
        for step in descriptor.step_statuses
    ]
    payload = descriptor.model_dump(mode="json")
    payload.update(
        {
            "flow_status": resulting_status.value,
            "current_step_id": current_step_id,
            "checkpoint_refs": checkpoint_refs,
            "step_statuses": [step.model_dump(mode="json") for step in step_statuses],
            "updated_at": updated_at,
        }
    )
    return WorkflowPackTaskFlowDescriptor.model_validate(payload)


def _append_checkpoint_to_step(
    step: WorkflowPackTaskFlowStepDescriptor,
    checkpoint: WorkflowPackTaskFlowCheckpointDescriptor,
) -> WorkflowPackTaskFlowStepDescriptor:
    if step.step_id != checkpoint.step_id:
        return step
    checkpoint_refs = [*step.checkpoint_refs]
    if checkpoint.checkpoint_id not in checkpoint_refs:
        checkpoint_refs.append(checkpoint.checkpoint_id)
    return step.model_copy(deep=True, update={"checkpoint_refs": checkpoint_refs})
