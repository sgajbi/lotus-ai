from __future__ import annotations

from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCatalogResponse,
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowCheckpointCatalogResponse,
    WorkflowPackTaskFlowDetailResponse,
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowStatus,
    WorkflowPackTaskFlowStepDescriptor,
)
from app.contracts.workflow_pack_runs import WorkflowPackRunSupportabilityStatus
from app.config import settings
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


TASK_FLOW_ACTIVE_STATUSES = {
    WorkflowPackTaskFlowStatus.CREATED,
    WorkflowPackTaskFlowStatus.RUNNING,
    WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT,
    WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
    WorkflowPackTaskFlowStatus.BLOCKED,
}

TASK_FLOW_TERMINAL_STATUSES = {
    WorkflowPackTaskFlowStatus.COMPLETED,
    WorkflowPackTaskFlowStatus.FAILED,
    WorkflowPackTaskFlowStatus.CANCELLED,
    WorkflowPackTaskFlowStatus.EXPIRED,
    WorkflowPackTaskFlowStatus.SUPERSEDED,
}


def ensure_workflow_pack_task_flow_store_ready() -> None:
    status_descriptor = get_workflow_pack_task_flow_store_runtime_status()
    if status_descriptor.status != RuntimeReadinessStatus.READY:
        raise WorkflowPackTaskFlowStoreNotReadyError(
            "Workflow-pack task-flow store is not ready. "
            f"Current status is `{status_descriptor.status.value}`. {status_descriptor.detail}",
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


def build_workflow_pack_task_flow_catalog(
    *,
    workflow_pack_id: str | None = None,
    caller: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    flow_status: WorkflowPackTaskFlowStatus | None = None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None = None,
    limit: int = 100,
) -> WorkflowPackTaskFlowCatalogResponse:
    task_flows = list_task_flows()
    filtered = _filter_task_flows(
        task_flows,
        workflow_pack_id=workflow_pack_id,
        caller=caller,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        flow_status=flow_status,
        supportability_status=supportability_status,
    )[:limit]
    return WorkflowPackTaskFlowCatalogResponse(
        service=settings.service_name,
        phase=settings.delivery_phase,
        task_flow_store_mode=settings.workflow_pack_task_flow_store_mode,
        task_flow_count=len(filtered),
        active_count=sum(flow.flow_status in TASK_FLOW_ACTIVE_STATUSES for flow in filtered),
        waiting_for_review_count=sum(
            flow.flow_status == WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW
            for flow in filtered
        ),
        blocked_count=sum(
            flow.flow_status == WorkflowPackTaskFlowStatus.BLOCKED for flow in filtered
        ),
        terminal_count=sum(flow.flow_status in TASK_FLOW_TERMINAL_STATUSES for flow in filtered),
        filters_applied=_filters_applied(
            workflow_pack_id=workflow_pack_id,
            caller=caller,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            flow_status=flow_status,
            supportability_status=supportability_status,
            limit=limit,
        ),
        task_flows=filtered,
    )


def build_workflow_pack_task_flow_detail(
    task_flow_id: str,
) -> WorkflowPackTaskFlowDetailResponse:
    task_flow = get_task_flow(task_flow_id)
    if task_flow is None:
        raise WorkflowPackTaskFlowNotFoundError(
            f"Unknown workflow-pack task flow: {task_flow_id}"
        )
    checkpoints = list_task_flow_checkpoints(task_flow_id)
    return WorkflowPackTaskFlowDetailResponse(
        service=settings.service_name,
        phase=settings.delivery_phase,
        task_flow_store_mode=settings.workflow_pack_task_flow_store_mode,
        task_flow=task_flow,
        checkpoints=checkpoints,
    )


def build_workflow_pack_task_flow_checkpoint_catalog(
    task_flow_id: str,
) -> WorkflowPackTaskFlowCheckpointCatalogResponse:
    if get_task_flow(task_flow_id) is None:
        raise WorkflowPackTaskFlowNotFoundError(
            f"Unknown workflow-pack task flow: {task_flow_id}"
        )
    checkpoints = list_task_flow_checkpoints(task_flow_id)
    return WorkflowPackTaskFlowCheckpointCatalogResponse(
        service=settings.service_name,
        phase=settings.delivery_phase,
        task_flow_store_mode=settings.workflow_pack_task_flow_store_mode,
        task_flow_id=task_flow_id,
        checkpoint_count=len(checkpoints),
        checkpoints=checkpoints,
    )


def _filter_task_flows(
    task_flows: list[WorkflowPackTaskFlowDescriptor],
    *,
    workflow_pack_id: str | None,
    caller: str | None,
    tenant_id: str | None,
    workflow_surface: str | None,
    flow_status: WorkflowPackTaskFlowStatus | None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None,
) -> list[WorkflowPackTaskFlowDescriptor]:
    return [
        task_flow
        for task_flow in task_flows
        if (workflow_pack_id is None or task_flow.workflow_pack_id == workflow_pack_id)
        and (caller is None or task_flow.caller == caller)
        and (tenant_id is None or task_flow.tenant_id == tenant_id)
        and (workflow_surface is None or task_flow.workflow_surface == workflow_surface)
        and (flow_status is None or task_flow.flow_status == flow_status)
        and (
            supportability_status is None
            or task_flow.supportability_status == supportability_status
        )
    ]


def _filters_applied(
    *,
    workflow_pack_id: str | None,
    caller: str | None,
    tenant_id: str | None,
    workflow_surface: str | None,
    flow_status: WorkflowPackTaskFlowStatus | None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None,
    limit: int,
) -> dict[str, object]:
    filters: dict[str, object] = {"limit": limit}
    if workflow_pack_id is not None:
        filters["workflow_pack_id"] = workflow_pack_id
    if caller is not None:
        filters["caller"] = caller
    if tenant_id is not None:
        filters["tenant_id"] = tenant_id
    if workflow_surface is not None:
        filters["workflow_surface"] = workflow_surface
    if flow_status is not None:
        filters["flow_status"] = flow_status.value
    if supportability_status is not None:
        filters["supportability_status"] = supportability_status.value
    return filters


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
