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
    WorkflowPackRunSupportabilityStatus,
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
from app.services.workflow_pack_run_supportability_summary import (
    build_workflow_pack_run_supportability_descriptor_from_record,
)
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_run_supportability import (
    resolve_workflow_pack_run_supportability_status,
)


def build_workflow_pack_run_catalog(
    *,
    registration_ref: str | None = None,
    pack_id: str | None = None,
    caller_app: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    runtime_state: WorkflowPackRunRuntimeState | None = None,
    review_state: WorkflowPackRunReviewState | None = None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None = None,
    workflow_authority_owner: str | None = None,
    limit: int = 100,
) -> WorkflowPackRunCatalogResponse:
    runs = [
        map_workflow_pack_run_record(record) for record in get_workflow_pack_run_store().list_runs()
    ]
    filtered_runs = _filter_workflow_pack_runs(
        runs=runs,
        registration_ref=registration_ref,
        pack_id=pack_id,
        caller_app=caller_app,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        runtime_state=runtime_state,
        review_state=review_state,
        supportability_status=supportability_status,
        workflow_authority_owner=workflow_authority_owner,
    )
    filtered_runs.sort(key=lambda item: item.created_at, reverse=True)
    limited_runs = filtered_runs[:limit]
    filters_applied: dict[str, str | int] = {"limit": limit}
    if registration_ref is not None:
        filters_applied["registration_ref"] = registration_ref
    if pack_id is not None:
        filters_applied["pack_id"] = pack_id
    if caller_app is not None:
        filters_applied["caller_app"] = caller_app
    if tenant_id is not None:
        filters_applied["tenant_id"] = tenant_id
    if workflow_surface is not None:
        filters_applied["workflow_surface"] = workflow_surface
    if runtime_state is not None:
        filters_applied["runtime_state"] = runtime_state.value
    if review_state is not None:
        filters_applied["review_state"] = review_state.value
    if supportability_status is not None:
        filters_applied["supportability_status"] = supportability_status.value
    if workflow_authority_owner is not None:
        filters_applied["workflow_authority_owner"] = workflow_authority_owner
    runs_with_supportability = [
        (run, resolve_workflow_pack_run_supportability_status(run)) for run in limited_runs
    ]
    return WorkflowPackRunCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        run_store_mode=settings.workflow_pack_run_store_mode,
        run_count=len(limited_runs),
        filters_applied=filters_applied,
        awaiting_review_count=sum(
            1
            for run in limited_runs
            if run.review_state == WorkflowPackRunReviewState.AWAITING_REVIEW
        ),
        completed_count=sum(
            1
            for run in limited_runs
            if run.runtime_state == WorkflowPackRunRuntimeState.COMPLETED
        ),
        ready_count=sum(
            1
            for _, status in runs_with_supportability
            if status is WorkflowPackRunSupportabilityStatus.READY
        ),
        action_required_count=sum(
            1
            for _, status in runs_with_supportability
            if status is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
        ),
        historical_count=sum(
            1
            for _, status in runs_with_supportability
            if status is WorkflowPackRunSupportabilityStatus.HISTORICAL
        ),
        latest_recorded_at=limited_runs[0].created_at if limited_runs else None,
        runs=limited_runs,
        notes=[
            "Workflow-pack run records are reference-oriented and preserve runtime state separately from review state.",
            "The current slice records Phase-1 workflow-pack executions through an explicit execution seam and a narrower binding-backed task fallback while the broader workflow-pack runtime remains under implementation.",
            "Catalog queries are now bounded and can be filtered by registration, caller identity, workflow surface, workflow-authority owner, runtime state, review state, and shared supportability posture for operator triage.",
            "Supportability counts are computed server-side from the same shared run-supportability seam used by runtime status and operator profiles.",
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
        supportability=build_workflow_pack_run_supportability_descriptor_from_record(
            record=record,
            map_record=map_workflow_pack_run_record,
        ),
        events=[
            map_workflow_pack_run_event_record(event)
            for event in get_workflow_pack_run_store().list_events(run_id=run_id)
        ],
        notes=[
            "Runtime state and review state are modeled separately in the run detail to avoid ambiguous operator or product interpretation.",
            "Supportability posture is included alongside the raw run record so callers do not need a separate profile request just to understand readiness versus action-required or historical posture.",
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


def _filter_workflow_pack_runs(
    *,
    runs: list[WorkflowPackRunDescriptor],
    registration_ref: str | None,
    pack_id: str | None,
    caller_app: str | None,
    tenant_id: str | None,
    workflow_surface: str | None,
    runtime_state: WorkflowPackRunRuntimeState | None,
    review_state: WorkflowPackRunReviewState | None,
    supportability_status: WorkflowPackRunSupportabilityStatus | None,
    workflow_authority_owner: str | None,
) -> list[WorkflowPackRunDescriptor]:
    filtered_runs = runs
    if registration_ref is not None:
        filtered_runs = [
            run for run in filtered_runs if run.registration_ref == registration_ref
        ]
    if pack_id is not None:
        filtered_runs = [run for run in filtered_runs if run.pack_id == pack_id]
    if caller_app is not None:
        filtered_runs = [run for run in filtered_runs if run.caller_app == caller_app]
    if tenant_id is not None:
        filtered_runs = [run for run in filtered_runs if run.tenant_id == tenant_id]
    if workflow_surface is not None:
        filtered_runs = [
            run for run in filtered_runs if run.workflow_surface == workflow_surface
        ]
    if runtime_state is not None:
        filtered_runs = [run for run in filtered_runs if run.runtime_state is runtime_state]
    if review_state is not None:
        filtered_runs = [run for run in filtered_runs if run.review_state is review_state]
    if supportability_status is not None:
        filtered_runs = [
            run
            for run in filtered_runs
            if resolve_workflow_pack_run_supportability_status(run).value
            == supportability_status.value
        ]
    if workflow_authority_owner is not None:
        filtered_runs = [
            run
            for run in filtered_runs
            if run.workflow_authority_owner == workflow_authority_owner
        ]
    return filtered_runs
