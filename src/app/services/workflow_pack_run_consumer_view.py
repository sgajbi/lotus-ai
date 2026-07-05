from __future__ import annotations

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunConsumerLineageDescriptor,
    WorkflowPackRunConsumerProvenanceDescriptor,
    WorkflowPackRunConsumerRuntimeDescriptor,
    WorkflowPackRunConsumerSupportabilityDescriptor,
    WorkflowPackRunConsumerViewResponse,
    WorkflowPackRunDescriptor,
    WorkflowPackRunRuntimeState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunRecord,
)
from app.services.workflow_pack_run_ledger import load_workflow_pack_run_context
from app.services.workflow_pack_run_output_summary import (
    build_idea_lineage_from_run_output_summary,
    load_workflow_pack_run_output_summary,
)
from app.services.workflow_pack_run_provenance_summary import (
    build_workflow_pack_run_provenance_summary,
)
from app.services.workflow_pack_run_review_summary import (
    build_workflow_pack_run_review_descriptor,
)
from app.services.workflow_pack_run_supportability_summary import (
    build_workflow_pack_run_supportability_descriptor,
)


def build_workflow_pack_run_consumer_view(*, run_id: str) -> WorkflowPackRunConsumerViewResponse:
    loaded = load_workflow_pack_run_context(run_id=run_id)

    return WorkflowPackRunConsumerViewResponse(
        service=settings.service_name,
        version=settings.service_version,
        run_store_mode=settings.workflow_pack_run_store_mode,
        runtime=_build_runtime_descriptor(loaded.record),
        review=build_workflow_pack_run_review_descriptor(
            record=loaded.record,
            events=loaded.events,
        ),
        lineage=_build_lineage_descriptor(loaded.record, run=loaded.run),
        provenance=_build_provenance_descriptor(loaded.record),
        provenance_summary=build_workflow_pack_run_provenance_summary(run=loaded.run),
        supportability=_build_supportability_descriptor(loaded.run),
        notes=[
            "This consumer view is a bounded contract candidate for downstream product surfaces and composition layers.",
            "Runtime posture and review posture remain separate so downstream consumers do not collapse AI lifecycle into one ambiguous status.",
            "Provenance linkage is summarized explicitly so downstream consumers can understand artifact and evidence posture without scanning every linked descriptor first.",
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


def _build_lineage_descriptor(
    record: WorkflowPackRunRecord,
    *,
    run: WorkflowPackRunDescriptor,
) -> WorkflowPackRunConsumerLineageDescriptor:
    artifact_payload = load_workflow_pack_run_output_summary(record.artifact_refs)
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
        recovery_lineage=run.recovery_lineage,
        idea_lineage=build_idea_lineage_from_run_output_summary(artifact_payload),
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
    run: WorkflowPackRunDescriptor,
) -> WorkflowPackRunConsumerSupportabilityDescriptor:
    return build_workflow_pack_run_supportability_descriptor(run=run)
