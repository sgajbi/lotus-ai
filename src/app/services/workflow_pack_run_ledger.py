from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.tasks import TaskExecutionResponse
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunCatalogResponse,
    WorkflowPackRunDescriptor,
    WorkflowPackRunDetailResponse,
    WorkflowPackRunEventDescriptor,
    WorkflowPackRunEventType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)
from app.services.task_execution_models import TaskExecutionContext
from app.services.workflow_pack_bindings import (
    resolve_workflow_pack_execution_binding_for_task,
)
from app.services.workflow_pack_run_artifacts import persist_workflow_pack_run_output_artifact
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions
from app.services.workflow_pack_run_store import get_workflow_pack_run_store


def build_workflow_pack_run_catalog() -> WorkflowPackRunCatalogResponse:
    runs = [
        map_workflow_pack_run_record(record) for record in get_workflow_pack_run_store().list_runs()
    ]
    runs.sort(key=lambda item: item.created_at, reverse=True)
    return WorkflowPackRunCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        run_store_mode=settings.workflow_pack_run_store_mode,
        run_count=len(runs),
        awaiting_review_count=sum(
            1 for run in runs if run.review_state == WorkflowPackRunReviewState.AWAITING_REVIEW
        ),
        completed_count=sum(
            1 for run in runs if run.runtime_state == WorkflowPackRunRuntimeState.COMPLETED
        ),
        latest_recorded_at=runs[0].created_at if runs else None,
        runs=runs,
        notes=[
            "Workflow-pack run records are reference-oriented and preserve runtime state separately from review state.",
            "The current slice records Phase-1 workflow-pack executions through an explicit execution seam and a narrower binding-backed task fallback while the broader workflow-pack runtime remains under implementation.",
            "Phase-1 recorded runs now emit governed workflow-pack artifact refs so support and downstream review can inspect bounded output summaries without pulling raw payloads into the ledger contract.",
        ],
    )


def build_workflow_pack_run_detail(*, run_id: str) -> WorkflowPackRunDetailResponse:
    record = get_workflow_pack_run_store().get_run(run_id=run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack run: {run_id}",
        )
    return WorkflowPackRunDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        run=map_workflow_pack_run_record(record),
        events=[
            map_workflow_pack_run_event_record(event)
            for event in get_workflow_pack_run_store().list_events(run_id=run_id)
        ],
        notes=[
            "Runtime state and review state are modeled separately in the run detail to avoid ambiguous operator or product interpretation.",
            "This run record preserves workflow-pack registration identity and workflow-authority ownership without claiming business approval authority for lotus-ai.",
        ],
    )


def record_workflow_pack_run_for_task_execution(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
) -> WorkflowPackRunDescriptor | None:
    resolved_binding = resolve_workflow_pack_execution_binding_for_task(context=context)
    if resolved_binding is None:
        return None

    return record_registered_workflow_pack_run(
        context=context,
        response=response,
        registration=resolved_binding.registration,
        workflow_surface=resolved_binding.binding.default_workflow_surface,
    )


def record_registered_workflow_pack_run(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
    registration: WorkflowPackRegistrationDescriptor,
    workflow_surface: str | None,
) -> WorkflowPackRunDescriptor:
    run_id = _build_workflow_pack_run_id(
        pack_family=registration.pack_family,
        request_id=context.request_id,
    )
    created_at = response.audit.generated_at
    review_required = registration.default_execution_mode.value == "REVIEW_GATED"
    review_state = (
        WorkflowPackRunReviewState.AWAITING_REVIEW
        if review_required
        else WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED
    )
    artifact_ref = persist_workflow_pack_run_output_artifact(
        run_id=run_id,
        context=context,
        response=response,
        pack_id=registration.pack_id,
        pack_version=registration.version,
        review_required=review_required,
        review_state=review_state.value,
        created_at=created_at,
    )
    record = WorkflowPackRunRecord(
        run_id=run_id,
        pack_id=registration.pack_id,
        pack_family=registration.pack_family,
        pack_version=registration.version,
        registration_ref=f"{registration.pack_id}@{registration.version}",
        task_id=response.task_id,
        request_id=context.request_id,
        caller_app=context.request.caller.caller_app,
        correlation_id=context.request.caller.correlation_id,
        tenant_id=context.request.caller.tenant_id,
        workflow_surface=workflow_surface,
        workflow_authority_owner=registration.workflow_authority_owner,
        runtime_state=WorkflowPackRunRuntimeState.COMPLETED.value,
        review_state=review_state.value,
        review_required=review_required,
        provider_mode=response.audit.provider_mode,
        stubbed=response.audit.stubbed,
        output_preview=response.result.message,
        structured_output_keys=sorted(response.result.structured_output.keys()),
        evidence_descriptors=[
            descriptor.model_copy(deep=True) for descriptor in response.evidence.descriptors
        ],
        artifact_refs=[artifact_ref],
        supersedes_run_id=None,
        superseded_by_run_id=None,
        created_at=created_at,
        completed_at=created_at,
        last_updated_at=created_at,
    )
    event = WorkflowPackRunEventRecord(
        event_id=f"{run_id}_event_recorded",
        run_id=run_id,
        event_type=WorkflowPackRunEventType.RUN_RECORDED.value,
        runtime_state=record.runtime_state,
        review_state=record.review_state,
        actor="lotus-ai.workflow-pack-run-ledger",
        message=(
            "Workflow-pack run recorded with runtime and review posture captured separately."
        ),
        recorded_at=created_at,
    )
    store = get_workflow_pack_run_store()
    store.save_run(record)
    store.save_event(event)
    return map_workflow_pack_run_record(record)


def build_workflow_pack_run_id(*, pack_family: str, request_id: str) -> str:
    return _build_workflow_pack_run_id(pack_family=pack_family, request_id=request_id)


def _build_workflow_pack_run_id(*, pack_family: str, request_id: str) -> str:
    return f"packrun_{pack_family}_{request_id}"


def map_workflow_pack_run_record(record: WorkflowPackRunRecord) -> WorkflowPackRunDescriptor:
    return WorkflowPackRunDescriptor(
        run_id=record.run_id,
        pack_id=record.pack_id,
        pack_family=record.pack_family,
        pack_version=record.pack_version,
        registration_ref=record.registration_ref,
        task_id=record.task_id,
        request_id=record.request_id,
        caller_app=record.caller_app,
        correlation_id=record.correlation_id,
        tenant_id=record.tenant_id,
        workflow_surface=record.workflow_surface,
        workflow_authority_owner=record.workflow_authority_owner,
        runtime_state=WorkflowPackRunRuntimeState(record.runtime_state),
        review_state=WorkflowPackRunReviewState(record.review_state),
        allowed_review_actions=resolve_allowed_review_actions(
            review_required=record.review_required,
            review_state=WorkflowPackRunReviewState(record.review_state),
        ),
        review_required=record.review_required,
        provider_mode=record.provider_mode,
        stubbed=record.stubbed,
        output_preview=record.output_preview,
        structured_output_keys=list(record.structured_output_keys),
        evidence_descriptors=[
            descriptor.model_copy(deep=True) for descriptor in record.evidence_descriptors
        ],
        artifact_refs=[artifact.model_copy(deep=True) for artifact in record.artifact_refs],
        supersedes_run_id=record.supersedes_run_id,
        superseded_by_run_id=record.superseded_by_run_id,
        created_at=record.created_at,
        completed_at=record.completed_at,
        last_updated_at=record.last_updated_at,
    )


def map_workflow_pack_run_event_record(
    record: WorkflowPackRunEventRecord,
) -> WorkflowPackRunEventDescriptor:
    return WorkflowPackRunEventDescriptor(
        event_id=record.event_id,
        run_id=record.run_id,
        event_type=WorkflowPackRunEventType(record.event_type),
        runtime_state=WorkflowPackRunRuntimeState(record.runtime_state),
        review_state=WorkflowPackRunReviewState(record.review_state),
        actor=record.actor,
        message=record.message,
        recorded_at=record.recorded_at,
    )
