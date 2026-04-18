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
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_run_store import get_workflow_pack_run_store


def build_workflow_pack_run_catalog() -> WorkflowPackRunCatalogResponse:
    runs = [_map_run_record(record) for record in get_workflow_pack_run_store().list_runs()]
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
            "The current slice records Phase-1 advisor-brief executions through the existing bounded task path while the broader workflow-pack runtime remains under implementation.",
            "Artifact references are supported in the ledger contract even when the current seeded runs do not yet emit durable workflow-pack artifacts.",
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
        run=_map_run_record(record),
        events=[
            _map_event_record(event)
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
    registration = _resolve_registration_for_task_execution(context=context)
    if registration is None:
        return None

    run_id = f"packrun_{registration.pack_family}_{context.request_id}"
    created_at = response.audit.generated_at
    review_required = registration.default_execution_mode.value == "REVIEW_GATED"
    review_state = (
        WorkflowPackRunReviewState.AWAITING_REVIEW
        if review_required
        else WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED
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
        workflow_surface=None,
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
        artifact_refs=[],
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
            "Workflow-pack run recorded from the Phase-1 advisor-brief task execution path with "
            "runtime and review posture captured separately."
        ),
        recorded_at=created_at,
    )
    store = get_workflow_pack_run_store()
    store.save_run(record)
    store.save_event(event)
    return _map_run_record(record)


def _resolve_registration_for_task_execution(
    *,
    context: TaskExecutionContext,
) -> WorkflowPackRegistrationDescriptor | None:
    if context.capability.task_id != "explain.v1":
        return None
    if context.request.caller.caller_app != "lotus-gateway":
        return None
    if not _is_advisor_brief_payload(context.request.context.payload):
        return None
    return get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")


def _is_advisor_brief_payload(payload: dict[str, object]) -> bool:
    return {"portfolio", "period", "performance", "supportability"}.issubset(payload.keys())


def _map_run_record(record: WorkflowPackRunRecord) -> WorkflowPackRunDescriptor:
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


def _map_event_record(record: WorkflowPackRunEventRecord) -> WorkflowPackRunEventDescriptor:
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
