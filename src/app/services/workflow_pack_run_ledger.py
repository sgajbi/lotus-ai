from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.contracts.tasks import TaskExecutionResponse
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunRecoveryActionType,
    WorkflowPackRunRecoveryLineageDescriptor,
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
    WorkflowPackRunRepository,
)
from app.contracts.tasks import TaskExecutionStatus
from app.services.task_execution_models import TaskExecutionContext
from app.services.workflow_pack_bindings import (
    ResolvedWorkflowPackExecutionBinding,
    resolve_workflow_pack_execution_binding_for_task,
)
from app.services.workflow_pack_run_artifacts import persist_workflow_pack_run_output_artifact
from app.services.workflow_run_attestation_source import (
    capture_workflow_run_attestation_source,
)
from app.services.workflow_run_model_risk import evaluate_workflow_run_model_risk_from_catalogue
from app.services.workflow_pack_run_provenance_summary import (
    build_workflow_pack_run_provenance_summary,
)
from app.services.workflow_pack_run_supportability_summary import (
    build_workflow_pack_run_supportability_descriptor,
)
from app.services.workflow_pack_run_review_summary import (
    build_workflow_pack_run_review_descriptor,
    build_workflow_pack_run_review_summary,
)
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_run_supportability import (
    resolve_workflow_pack_run_record_supportability_status,
)
from app.services.runtime_readiness import get_workflow_pack_run_store_runtime_status


@dataclass(frozen=True)
class WorkflowPackRunLoadedContext:
    record: WorkflowPackRunRecord
    run: WorkflowPackRunDescriptor
    events: list[WorkflowPackRunEventRecord]


class WorkflowPackRunStoreUnavailableError(RuntimeError):
    pass


RUN_CATALOG_QUERY_WINDOW_MULTIPLIER = 10
RUN_CATALOG_QUERY_WINDOW_MAX = 500


def load_workflow_pack_run_context(*, run_id: str) -> WorkflowPackRunLoadedContext:
    ensure_workflow_pack_run_store_ready()
    store = get_workflow_pack_run_store()
    record = store.get_run(run_id=run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack run: {run_id}",
        )
    return WorkflowPackRunLoadedContext(
        record=record,
        run=map_workflow_pack_run_record(record, store=store),
        events=store.list_events(run_id=run_id),
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
    ensure_workflow_pack_run_store_ready()
    store = get_workflow_pack_run_store()
    source_run_limit = _run_catalog_query_limit(
        limit=limit,
        supportability_status=supportability_status,
    )
    source_records = store.query_runs(
        registration_ref=registration_ref,
        pack_id=pack_id,
        caller_app=caller_app,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        runtime_state=runtime_state.value if runtime_state is not None else None,
        review_state=review_state.value if review_state is not None else None,
        workflow_authority_owner=workflow_authority_owner,
        limit=source_run_limit,
    )
    runs = [map_workflow_pack_run_record(record, store=store) for record in source_records]
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
    filters_applied["source_run_limit"] = source_run_limit
    filters_applied["source_run_count"] = len(source_records)
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
    runs_with_supportability = [(run, run.supportability_status) for run in limited_runs]
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
            1 for run in limited_runs if run.runtime_state == WorkflowPackRunRuntimeState.COMPLETED
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
            "Supportability counts and per-run status fields are computed server-side from the same shared run-supportability seam used by runtime status and operator profiles.",
            "Phase-1 recorded runs now emit governed workflow-pack artifact refs so support and downstream review can inspect bounded output summaries without pulling raw payloads into the ledger contract.",
        ],
    )


def _run_catalog_query_limit(
    *,
    limit: int,
    supportability_status: WorkflowPackRunSupportabilityStatus | None,
) -> int:
    bounded_limit = max(limit, 0)
    if supportability_status is None:
        return bounded_limit
    return min(
        max(bounded_limit * RUN_CATALOG_QUERY_WINDOW_MULTIPLIER, bounded_limit),
        RUN_CATALOG_QUERY_WINDOW_MAX,
    )


def build_workflow_pack_run_detail(*, run_id: str) -> WorkflowPackRunDetailResponse:
    loaded = load_workflow_pack_run_context(run_id=run_id)
    return WorkflowPackRunDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        run=loaded.run,
        review=build_workflow_pack_run_review_descriptor(
            record=loaded.record,
            events=loaded.events,
        ),
        provenance=build_workflow_pack_run_provenance_summary(run=loaded.run),
        supportability=build_workflow_pack_run_supportability_descriptor(run=loaded.run),
        events=[map_workflow_pack_run_event_record(event) for event in loaded.events],
        notes=[
            "Runtime state and review state are modeled separately in the run detail to avoid ambiguous operator or product interpretation.",
            "Review progression posture is summarized alongside the raw event history so callers do not need to parse review events just to understand bounded review metadata.",
            "Artifact and evidence linkage are summarized alongside the raw run record so callers can understand provenance posture without scanning every linked descriptor first.",
            "Supportability posture is included alongside the raw run record so callers do not need a separate profile request just to understand readiness versus action-required or historical posture.",
            "This run record preserves workflow-pack registration identity and workflow-authority ownership without claiming business approval authority for lotus-ai.",
        ],
    )


def record_workflow_pack_run_for_task_execution(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
    resolved_binding: ResolvedWorkflowPackExecutionBinding | None = None,
) -> WorkflowPackRunDescriptor | None:
    pack_binding = resolved_binding or resolve_workflow_pack_execution_binding_for_task(
        context=context
    )
    if pack_binding is None:
        return None

    return record_registered_workflow_pack_run(
        context=context,
        response=response,
        registration=pack_binding.registration,
        workflow_surface=pack_binding.binding.default_workflow_surface,
    )


def record_registered_workflow_pack_run(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
    registration: WorkflowPackRegistrationDescriptor,
    workflow_surface: str | None,
    recovery_lineage: WorkflowPackRunRecoveryLineageDescriptor | None = None,
) -> WorkflowPackRunDescriptor:
    ensure_workflow_pack_run_store_ready()
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
    model_risk_decision = evaluate_workflow_run_model_risk_from_catalogue(
        provider_id=response.audit.provider_id,
        provider_mode=response.audit.provider_mode,
        model_id=response.audit.model_id or "deterministic-stub",
        model_version=response.audit.model_version
        or ("stub.v1" if response.audit.stubbed else "model-version-unavailable"),
        workflow_pack_id=registration.pack_id,
        evaluated_at_utc=response.audit.generated_at,
        stubbed=response.audit.stubbed,
    )
    attestation_source = capture_workflow_run_attestation_source(
        run_id=run_id,
        context=context,
        response=response,
        registration=registration,
        model_risk_status=model_risk_decision.status,
        model_risk_approval_ref=model_risk_decision.approval_ref,
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
        runtime_state=_resolve_runtime_state(response).value,
        review_state=review_state.value,
        review_required=review_required,
        provider_mode=response.audit.provider_mode,
        provider_config_sha256=response.audit.provider_config_sha256,
        stubbed=response.audit.stubbed,
        output_preview=response.result.message,
        structured_output_keys=sorted(response.result.structured_output.keys()),
        evidence_descriptors=[
            descriptor.model_copy(deep=True) for descriptor in response.evidence.descriptors
        ],
        artifact_refs=[artifact_ref],
        supersedes_run_id=None,
        superseded_by_run_id=None,
        recovery_action_type=(
            recovery_lineage.recovery_action_type.value if recovery_lineage is not None else None
        ),
        source_queue_item_id=(
            recovery_lineage.source_queue_item_id if recovery_lineage is not None else None
        ),
        recovery_decision_event_id=(
            recovery_lineage.recovery_decision_event_id if recovery_lineage is not None else None
        ),
        recovery_attempt_number=(
            recovery_lineage.recovery_attempt_number if recovery_lineage is not None else None
        ),
        source_workflow_pack_run_id=(
            recovery_lineage.source_workflow_pack_run_id if recovery_lineage is not None else None
        ),
        recovery_requested_by=(
            recovery_lineage.requested_by if recovery_lineage is not None else None
        ),
        recovery_evidence_ref=(
            recovery_lineage.evidence_ref if recovery_lineage is not None else None
        ),
        evaluator_id=attestation_source.evaluator_id,
        evaluator_policy_version=attestation_source.evaluator_policy_version,
        provider_id=attestation_source.provider_id,
        model_id=attestation_source.model_id,
        model_version=attestation_source.model_version,
        model_risk_status=attestation_source.model_risk_status,
        model_risk_approval_ref=attestation_source.model_risk_approval_ref,
        input_evidence_sha256=attestation_source.input_evidence_sha256,
        output_content_sha256=attestation_source.output_content_sha256,
        replay_nonce=attestation_source.replay_nonce,
        execution_started_at=context.execution_started_at,
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
        message=("Workflow-pack run recorded with runtime and review posture captured separately."),
        recorded_at=created_at,
    )
    store = get_workflow_pack_run_store()
    store.save_run(record)
    store.save_event(event)
    return map_workflow_pack_run_record(record)


def build_workflow_pack_run_id(*, pack_family: str, request_id: str) -> str:
    return _build_workflow_pack_run_id(pack_family=pack_family, request_id=request_id)


def ensure_workflow_pack_run_store_ready() -> None:
    status_descriptor = get_workflow_pack_run_store_runtime_status()
    if status_descriptor.status is RuntimeReadinessStatus.READY:
        return
    raise WorkflowPackRunStoreUnavailableError(
        "Workflow-pack run store is not ready. "
        f"Current status is `{status_descriptor.status.value}`. {status_descriptor.detail}"
    )


def _build_workflow_pack_run_id(*, pack_family: str, request_id: str) -> str:
    return f"packrun_{pack_family}_{request_id}"


def _resolve_runtime_state(response: TaskExecutionResponse) -> WorkflowPackRunRuntimeState:
    if response.status is TaskExecutionStatus.FAILED:
        return WorkflowPackRunRuntimeState.FAILED
    return WorkflowPackRunRuntimeState.COMPLETED


def map_workflow_pack_run_record(
    record: WorkflowPackRunRecord,
    *,
    store: WorkflowPackRunRepository | None = None,
) -> WorkflowPackRunDescriptor:
    run_store = store or get_workflow_pack_run_store()
    review_summary = build_workflow_pack_run_review_summary(
        events=run_store.list_events(run_id=record.run_id)
    )
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
        supportability_status=resolve_workflow_pack_run_record_supportability_status(record),
        allowed_review_actions=resolve_allowed_review_actions(
            review_required=record.review_required,
            review_state=WorkflowPackRunReviewState(record.review_state),
            runtime_state=WorkflowPackRunRuntimeState(record.runtime_state),
        ),
        review_summary=review_summary,
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
        replacement_run_id=record.superseded_by_run_id,
        recovery_lineage=_build_recovery_lineage_descriptor(record),
        created_at=record.created_at,
        completed_at=record.completed_at,
        last_updated_at=record.last_updated_at,
    )


def _build_recovery_lineage_descriptor(
    record: WorkflowPackRunRecord,
) -> WorkflowPackRunRecoveryLineageDescriptor | None:
    if (
        record.recovery_action_type is None
        or record.source_queue_item_id is None
        or record.recovery_decision_event_id is None
    ):
        return None
    return WorkflowPackRunRecoveryLineageDescriptor(
        recovery_action_type=WorkflowPackRunRecoveryActionType(record.recovery_action_type),
        source_queue_item_id=record.source_queue_item_id,
        recovery_decision_event_id=record.recovery_decision_event_id,
        recovery_attempt_number=record.recovery_attempt_number,
        source_workflow_pack_run_id=record.source_workflow_pack_run_id,
        requested_by=record.recovery_requested_by,
        evidence_ref=record.recovery_evidence_ref,
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
        filtered_runs = [run for run in filtered_runs if run.registration_ref == registration_ref]
    if pack_id is not None:
        filtered_runs = [run for run in filtered_runs if run.pack_id == pack_id]
    if caller_app is not None:
        filtered_runs = [run for run in filtered_runs if run.caller_app == caller_app]
    if tenant_id is not None:
        filtered_runs = [run for run in filtered_runs if run.tenant_id == tenant_id]
    if workflow_surface is not None:
        filtered_runs = [run for run in filtered_runs if run.workflow_surface == workflow_surface]
    if runtime_state is not None:
        filtered_runs = [run for run in filtered_runs if run.runtime_state is runtime_state]
    if review_state is not None:
        filtered_runs = [run for run in filtered_runs if run.review_state is review_state]
    if supportability_status is not None:
        filtered_runs = [
            run for run in filtered_runs if run.supportability_status is supportability_status
        ]
    if workflow_authority_owner is not None:
        filtered_runs = [
            run for run in filtered_runs if run.workflow_authority_owner == workflow_authority_owner
        ]
    return filtered_runs
