from __future__ import annotations

import hashlib

from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCatalogResponse,
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowCheckpointCatalogResponse,
    WorkflowPackTaskFlowCheckpointTransition,
    WorkflowPackTaskFlowDetailResponse,
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowHandoffDescriptor,
    WorkflowPackTaskFlowHandoffStatus,
    WorkflowPackTaskFlowReplacementLineageDescriptor,
    WorkflowPackTaskFlowStatus,
    WorkflowPackTaskFlowStepDescriptor,
)
from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunSupportabilityStatus,
)
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

GENERATED_IDENTIFIER_MAX_LENGTH = 128
GENERATED_IDENTIFIER_DIGEST_LENGTH = 24
TASK_FLOW_REVIEW_SYNC_RUN_REF_LIMIT = 20


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


def query_task_flows(
    *,
    workflow_pack_id: str | None = None,
    caller: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    flow_status: WorkflowPackTaskFlowStatus | None = None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None = None,
    limit: int = 100,
    store: WorkflowPackTaskFlowRepository | None = None,
) -> list[WorkflowPackTaskFlowDescriptor]:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = store or get_workflow_pack_task_flow_store()
    return [
        record.descriptor
        for record in task_flow_store.query_task_flows(
            workflow_pack_id=workflow_pack_id,
            caller=caller,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            flow_status=flow_status.value if flow_status is not None else None,
            supportability_status=(
                supportability_status.value if supportability_status is not None else None
            ),
            limit=limit,
        )
    ]


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
    filtered = query_task_flows(
        workflow_pack_id=workflow_pack_id,
        caller=caller,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        flow_status=flow_status,
        supportability_status=supportability_status,
        limit=limit,
    )
    return WorkflowPackTaskFlowCatalogResponse(
        service=settings.service_name,
        phase=settings.delivery_phase,
        task_flow_store_mode=settings.workflow_pack_task_flow_store_mode,
        task_flow_count=len(filtered),
        active_count=sum(flow.flow_status in TASK_FLOW_ACTIVE_STATUSES for flow in filtered),
        waiting_for_review_count=sum(
            flow.flow_status == WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW for flow in filtered
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
        raise WorkflowPackTaskFlowNotFoundError(f"Unknown workflow-pack task flow: {task_flow_id}")
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
        raise WorkflowPackTaskFlowNotFoundError(f"Unknown workflow-pack task flow: {task_flow_id}")
    checkpoints = list_task_flow_checkpoints(task_flow_id)
    return WorkflowPackTaskFlowCheckpointCatalogResponse(
        service=settings.service_name,
        phase=settings.delivery_phase,
        task_flow_store_mode=settings.workflow_pack_task_flow_store_mode,
        task_flow_id=task_flow_id,
        checkpoint_count=len(checkpoints),
        checkpoints=checkpoints,
    )


def synchronize_task_flow_review_action(
    *,
    run_id: str,
    review_state: WorkflowPackRunReviewState,
    supportability_status: WorkflowPackRunSupportabilityStatus,
    action_type: WorkflowPackRunReviewActionType,
    reviewed_by: str,
    reason: str,
    recorded_at: str,
    replacement_run_id: str | None = None,
) -> None:
    ensure_workflow_pack_task_flow_store_ready()
    task_flow_store = get_workflow_pack_task_flow_store()
    lineage = (
        WorkflowPackTaskFlowReplacementLineageDescriptor(
            superseded_run_id=run_id,
            replacement_run_id=replacement_run_id,
            review_action_ref=action_type.value,
            reason=reason,
        )
        if replacement_run_id is not None
        else None
    )
    task_flows = task_flow_store.list_task_flows_by_run_ref(
        run_id=run_id,
        limit=TASK_FLOW_REVIEW_SYNC_RUN_REF_LIMIT,
    )
    if replacement_run_id is not None:
        task_flows.extend(
            task_flow_store.list_task_flows_by_run_ref(
                run_id=replacement_run_id,
                limit=TASK_FLOW_REVIEW_SYNC_RUN_REF_LIMIT,
            )
        )
    seen_task_flow_ids: set[str] = set()
    for record in task_flows:
        task_flow = record.descriptor
        if task_flow.task_flow_id in seen_task_flow_ids:
            continue
        seen_task_flow_ids.add(task_flow.task_flow_id)
        if run_id in task_flow.run_refs:
            _record_review_checkpoint(
                task_flow_store=task_flow_store,
                task_flow=task_flow,
                run_id=run_id,
                review_state=review_state,
                supportability_status=supportability_status,
                action_type=action_type,
                reviewed_by=reviewed_by,
                reason=reason,
                recorded_at=recorded_at,
                lineage=lineage,
            )
            continue
        if replacement_run_id is not None and replacement_run_id in task_flow.run_refs:
            updated = _with_review_lineage(task_flow, lineage=lineage)
            task_flow_store.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=updated))


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


def _record_review_checkpoint(
    *,
    task_flow_store: WorkflowPackTaskFlowRepository,
    task_flow: WorkflowPackTaskFlowDescriptor,
    run_id: str,
    review_state: WorkflowPackRunReviewState,
    supportability_status: WorkflowPackRunSupportabilityStatus,
    action_type: WorkflowPackRunReviewActionType,
    reviewed_by: str,
    reason: str,
    recorded_at: str,
    lineage: WorkflowPackTaskFlowReplacementLineageDescriptor | None,
) -> WorkflowPackTaskFlowDescriptor:
    resulting_status = _resolve_review_task_flow_status(action_type)
    step_id = task_flow.current_step_id or task_flow.step_statuses[0].step_id
    checkpoint_id = _bounded_generated_identifier(
        f"{task_flow.task_flow_id}_review_{run_id}_{action_type.value.lower()}",
        readable_prefix=f"task_flow_review_{action_type.value.lower()}",
    )
    checkpoint = WorkflowPackTaskFlowCheckpointDescriptor(
        checkpoint_id=checkpoint_id,
        task_flow_id=task_flow.task_flow_id,
        step_id=step_id,
        transition=_resolve_review_checkpoint_transition(action_type),
        actor=f"review:{reviewed_by}",
        recorded_at=recorded_at,
        evidence_refs=[
            ExecutionEvidenceDescriptor(
                evidence_type="workflow_pack_review_action",
                summary="Workflow-pack run review action synchronized into task-flow posture.",
                attributes={
                    "run_id": run_id,
                    "action_type": action_type.value,
                    "review_state": review_state.value,
                },
            )
        ],
        run_id=run_id,
        review_ref=run_id,
        reason=reason,
    )
    require_task_flow_transition_allowed(task_flow.flow_status, resulting_status)
    updated = _append_checkpoint_to_task_flow(
        task_flow,
        checkpoint=checkpoint,
        resulting_status=resulting_status,
        current_step_id=(
            step_id
            if resulting_status
            in {
                WorkflowPackTaskFlowStatus.RUNNING,
                WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT,
                WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
                WorkflowPackTaskFlowStatus.BLOCKED,
            }
            else None
        ),
        updated_at=recorded_at,
    )
    updated = _with_review_state_and_lineage(
        updated,
        run_id=run_id,
        review_state=review_state,
        supportability_status=supportability_status,
        action_type=action_type,
        reason=reason,
        lineage=lineage,
    )
    task_flow_store.save_checkpoint(WorkflowPackTaskFlowCheckpointRecord(descriptor=checkpoint))
    task_flow_store.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=updated))
    return updated


def _with_review_state_and_lineage(
    task_flow: WorkflowPackTaskFlowDescriptor,
    *,
    run_id: str,
    review_state: WorkflowPackRunReviewState,
    supportability_status: WorkflowPackRunSupportabilityStatus,
    action_type: WorkflowPackRunReviewActionType,
    reason: str,
    lineage: WorkflowPackTaskFlowReplacementLineageDescriptor | None,
) -> WorkflowPackTaskFlowDescriptor:
    payload = task_flow.model_dump(mode="json")
    review_states = dict(payload["review_states"])
    review_states[run_id] = review_state.value
    payload["review_states"] = review_states
    payload["supportability_status"] = supportability_status.value
    if lineage is not None:
        payload["replacement_lineage"] = _append_lineage_payload(task_flow, lineage=lineage)
    if action_type is WorkflowPackRunReviewActionType.ACCEPT:
        payload["handoff_refs"] = _append_ready_handoff_payload(
            task_flow,
            run_id=run_id,
            reason=reason,
        )
    return WorkflowPackTaskFlowDescriptor.model_validate(payload)


def _with_review_lineage(
    task_flow: WorkflowPackTaskFlowDescriptor,
    *,
    lineage: WorkflowPackTaskFlowReplacementLineageDescriptor | None,
) -> WorkflowPackTaskFlowDescriptor:
    if lineage is None:
        return task_flow
    payload = task_flow.model_dump(mode="json")
    payload["replacement_lineage"] = _append_lineage_payload(task_flow, lineage=lineage)
    return WorkflowPackTaskFlowDescriptor.model_validate(payload)


def _append_lineage_payload(
    task_flow: WorkflowPackTaskFlowDescriptor,
    *,
    lineage: WorkflowPackTaskFlowReplacementLineageDescriptor,
) -> list[dict[str, object]]:
    lineage_payload = [item.model_dump(mode="json") for item in task_flow.replacement_lineage]
    candidate = lineage.model_dump(mode="json")
    if candidate not in lineage_payload:
        lineage_payload.append(candidate)
    return lineage_payload


def _append_ready_handoff_payload(
    task_flow: WorkflowPackTaskFlowDescriptor,
    *,
    run_id: str,
    reason: str,
) -> list[dict[str, object]]:
    handoff_payload = [item.model_dump(mode="json") for item in task_flow.handoff_refs]
    handoff_id = _bounded_generated_identifier(
        f"{task_flow.task_flow_id}_handoff_{run_id}",
        readable_prefix="task_flow_handoff_ready",
    )
    candidate = WorkflowPackTaskFlowHandoffDescriptor(
        handoff_id=handoff_id,
        owner_service=task_flow.workflow_authority_owner,
        status=WorkflowPackTaskFlowHandoffStatus.READY_FOR_HANDOFF,
        domain_ref=None,
        evidence_refs=[
            ExecutionEvidenceDescriptor(
                evidence_type="workflow_pack_review_handoff_ready",
                summary="Accepted workflow-pack task flow is ready for domain-owner handoff.",
                attributes={
                    "run_id": run_id,
                    "task_flow_id": task_flow.task_flow_id,
                    "workflow_authority_owner": task_flow.workflow_authority_owner,
                    "reason": reason,
                },
            )
        ],
    ).model_dump(mode="json")
    if candidate not in handoff_payload:
        handoff_payload.append(candidate)
    return handoff_payload


def _bounded_generated_identifier(
    raw_identifier: str,
    *,
    readable_prefix: str,
    max_length: int = GENERATED_IDENTIFIER_MAX_LENGTH,
) -> str:
    if len(raw_identifier) <= max_length:
        return raw_identifier

    digest = hashlib.sha256(raw_identifier.encode("utf-8")).hexdigest()[
        :GENERATED_IDENTIFIER_DIGEST_LENGTH
    ]
    suffix = f"_{digest}"
    prefix_budget = max_length - len(suffix)
    return f"{readable_prefix[:prefix_budget]}{suffix}"


def _resolve_review_task_flow_status(
    action_type: WorkflowPackRunReviewActionType,
) -> WorkflowPackTaskFlowStatus:
    if action_type == WorkflowPackRunReviewActionType.ACCEPT:
        return WorkflowPackTaskFlowStatus.COMPLETED
    if action_type == WorkflowPackRunReviewActionType.REJECT:
        return WorkflowPackTaskFlowStatus.FAILED
    if action_type in {
        WorkflowPackRunReviewActionType.REVISE,
        WorkflowPackRunReviewActionType.SUPERSEDE,
    }:
        return WorkflowPackTaskFlowStatus.SUPERSEDED
    if action_type == WorkflowPackRunReviewActionType.ABANDON:
        return WorkflowPackTaskFlowStatus.CANCELLED
    return WorkflowPackTaskFlowStatus.BLOCKED


def _resolve_review_checkpoint_transition(
    action_type: WorkflowPackRunReviewActionType,
) -> WorkflowPackTaskFlowCheckpointTransition:
    if action_type == WorkflowPackRunReviewActionType.ACCEPT:
        return WorkflowPackTaskFlowCheckpointTransition.FLOW_COMPLETED
    if action_type == WorkflowPackRunReviewActionType.REJECT:
        return WorkflowPackTaskFlowCheckpointTransition.STEP_FAILED
    if action_type == WorkflowPackRunReviewActionType.REVISE:
        return WorkflowPackTaskFlowCheckpointTransition.REVISION_REQUESTED
    if action_type == WorkflowPackRunReviewActionType.SUPERSEDE:
        return WorkflowPackTaskFlowCheckpointTransition.FLOW_SUPERSEDED
    if action_type == WorkflowPackRunReviewActionType.ABANDON:
        return WorkflowPackTaskFlowCheckpointTransition.FLOW_CANCELLED
    return WorkflowPackTaskFlowCheckpointTransition.FLOW_BLOCKED


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
        _append_checkpoint_to_step(step, checkpoint) for step in descriptor.step_statuses
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
