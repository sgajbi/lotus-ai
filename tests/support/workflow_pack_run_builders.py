from __future__ import annotations

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDescriptor,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewSummaryDescriptor,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.services.workflow_pack_run_supportability import resolve_workflow_pack_run_supportability_status


def build_workflow_pack_run_descriptor(
    *,
    run_id: str,
    runtime_state: WorkflowPackRunRuntimeState = WorkflowPackRunRuntimeState.COMPLETED,
    review_state: WorkflowPackRunReviewState = WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
    allowed_review_actions: list[WorkflowPackRunReviewActionType] | None = None,
    superseded_by_run_id: str | None = None,
    created_at: str = "2026-04-19T10:00:00Z",
    evidence_descriptors_count: int = 0,
    artifact_refs_count: int = 0,
    supportability_status: WorkflowPackRunSupportabilityStatus | None = None,
    latest_review_event_at: str | None = None,
    latest_review_actor: str | None = None,
    review_transition_count: int = 0,
) -> WorkflowPackRunDescriptor:
    descriptor = WorkflowPackRunDescriptor(
        run_id=run_id,
        pack_id="advisor_brief.pack",
        pack_family="advisor_brief",
        pack_version="v1",
        registration_ref="advisor_brief.pack@v1",
        task_id="explain.v1",
        request_id=f"req-{run_id}",
        caller_app="lotus-gateway",
        correlation_id=f"corr-{run_id}",
        tenant_id=None,
        workflow_surface="advisor-brief-workspace",
        workflow_authority_owner="lotus-gateway",
        runtime_state=runtime_state,
        review_state=review_state,
        supportability_status=WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        allowed_review_actions=allowed_review_actions or [],
        review_summary=WorkflowPackRunReviewSummaryDescriptor(
            latest_review_event_at=latest_review_event_at,
            latest_review_actor=latest_review_actor,
            review_transition_count=review_transition_count,
            has_review_history=review_transition_count > 0,
        ),
        review_required=review_state is not WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
        provider_mode="catalog_only",
        stubbed=True,
        output_preview="preview",
        structured_output_keys=["advisor_brief_status"],
        evidence_descriptors=[
            ExecutionEvidenceDescriptor(
                evidence_type=f"evidence_{index}",
                summary=f"Evidence {index}",
                attributes={"source": "test"},
            )
            for index in range(evidence_descriptors_count)
        ],
        artifact_refs=[
            ArtifactDescriptor(
                artifact_id=f"artifact_{index}",
                domain="workflow_pack",
                artifact_type="run_output_summary",
                source_object_kind="workflow_pack_run",
                source_object_id=run_id,
                lifecycle_status="runtime_generated",
                retention_posture="retained_for_review",
                media_type="application/json",
                byte_size=128,
                checksum_sha256=f"sha256:{index}",
                storage_backend="memory",
                storage_reference=f"memory://{run_id}/{index}",
                created_at=created_at,
                created_by="test",
            )
            for index in range(artifact_refs_count)
        ],
        supersedes_run_id=None,
        superseded_by_run_id=superseded_by_run_id,
        created_at=created_at,
        completed_at=created_at,
        last_updated_at=created_at,
    )
    resolved_status = supportability_status or resolve_workflow_pack_run_supportability_status(
        descriptor
    )
    return descriptor.model_copy(update={"supportability_status": resolved_status})
