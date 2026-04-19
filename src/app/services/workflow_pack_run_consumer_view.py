from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunConsumerLineageDescriptor,
    WorkflowPackRunConsumerProvenanceDescriptor,
    WorkflowPackRunConsumerReviewDescriptor,
    WorkflowPackRunConsumerRuntimeDescriptor,
    WorkflowPackRunConsumerSupportabilityDescriptor,
    WorkflowPackRunConsumerViewResponse,
    WorkflowPackRunEventType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions
from app.services.workflow_pack_run_ledger import map_workflow_pack_run_record
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_run_supportability_summary import (
    build_workflow_pack_run_supportability_descriptor,
)


def build_workflow_pack_run_consumer_view(*, run_id: str) -> WorkflowPackRunConsumerViewResponse:
    store = get_workflow_pack_run_store()
    record = store.get_run(run_id=run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack run: {run_id}",
        )
    events = store.list_events(run_id=run_id)

    return WorkflowPackRunConsumerViewResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        runtime=_build_runtime_descriptor(record),
        review=_build_review_descriptor(record, events),
        lineage=_build_lineage_descriptor(record),
        provenance=_build_provenance_descriptor(record),
        supportability=_build_supportability_descriptor(record),
        notes=[
            "This consumer view is a bounded contract candidate for downstream product surfaces and composition layers.",
            "Runtime posture and review posture remain separate so downstream consumers do not collapse AI lifecycle into one ambiguous status.",
            "Supportability posture is grouped explicitly so downstream consumers do not infer readiness or historical status from raw runtime and review states alone.",
            "Allowed review actions describe ledger-compatible transitions only and do not transfer consequence-bearing workflow authority.",
        ],
    )


def _build_runtime_descriptor(
    record: WorkflowPackRunRecord,
) -> WorkflowPackRunConsumerRuntimeDescriptor:
    return WorkflowPackRunConsumerRuntimeDescriptor(
        state=WorkflowPackRunRuntimeState(record.runtime_state),
        created_at=record.created_at,
        completed_at=record.completed_at,
        last_updated_at=record.last_updated_at,
        provider_mode=record.provider_mode,
        stubbed=record.stubbed,
    )


def _build_review_descriptor(
    record: WorkflowPackRunRecord,
    events: list[WorkflowPackRunEventRecord],
) -> WorkflowPackRunConsumerReviewDescriptor:
    review_state = WorkflowPackRunReviewState(record.review_state)
    latest_review_event = _resolve_latest_review_event(events)
    return WorkflowPackRunConsumerReviewDescriptor(
        required=record.review_required,
        state=review_state,
        allowed_actions=resolve_allowed_review_actions(
            review_required=record.review_required,
            review_state=review_state,
        ),
        latest_review_event_at=(
            latest_review_event.recorded_at if latest_review_event is not None else None
        ),
        latest_review_actor=latest_review_event.actor if latest_review_event is not None else None,
    )


def _build_lineage_descriptor(
    record: WorkflowPackRunRecord,
) -> WorkflowPackRunConsumerLineageDescriptor:
    return WorkflowPackRunConsumerLineageDescriptor(
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
        supersedes_run_id=record.supersedes_run_id,
        superseded_by_run_id=record.superseded_by_run_id,
    )


def _build_provenance_descriptor(
    record: WorkflowPackRunRecord,
) -> WorkflowPackRunConsumerProvenanceDescriptor:
    return WorkflowPackRunConsumerProvenanceDescriptor(
        output_preview=record.output_preview,
        structured_output_keys=list(record.structured_output_keys),
        evidence_descriptors=[
            descriptor.model_copy(deep=True) for descriptor in record.evidence_descriptors
        ],
        artifact_refs=[artifact.model_copy(deep=True) for artifact in record.artifact_refs],
    )


def _build_supportability_descriptor(
    record: WorkflowPackRunRecord,
) -> WorkflowPackRunConsumerSupportabilityDescriptor:
    return build_workflow_pack_run_supportability_descriptor(
        run=map_workflow_pack_run_record(record)
    )


def _resolve_latest_review_event(
    events: list[WorkflowPackRunEventRecord],
) -> WorkflowPackRunEventRecord | None:
    review_events = [
        event
        for event in events
        if event.event_type == WorkflowPackRunEventType.REVIEW_STATE_UPDATED.value
    ]
    if not review_events:
        return None
    return max(review_events, key=lambda event: event.recorded_at)
