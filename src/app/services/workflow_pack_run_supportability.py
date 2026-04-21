from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDescriptor,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord


def resolve_workflow_pack_run_supportability_status(
    run: WorkflowPackRunDescriptor,
) -> WorkflowPackRunSupportabilityStatus:
    return _resolve_workflow_pack_supportability_status(
        runtime_state=run.runtime_state,
        review_state=run.review_state,
        review_required=run.review_required,
        artifact_ref_count=len(run.artifact_refs),
        evidence_descriptor_count=len(run.evidence_descriptors),
        superseded_by_run_id=run.superseded_by_run_id,
    )


def resolve_workflow_pack_run_record_supportability_status(
    record: WorkflowPackRunRecord,
) -> WorkflowPackRunSupportabilityStatus:
    return _resolve_workflow_pack_supportability_status(
        runtime_state=WorkflowPackRunRuntimeState(record.runtime_state),
        review_state=WorkflowPackRunReviewState(record.review_state),
        review_required=record.review_required,
        artifact_ref_count=len(record.artifact_refs),
        evidence_descriptor_count=len(record.evidence_descriptors),
        superseded_by_run_id=record.superseded_by_run_id,
    )


def is_workflow_pack_run_review_pending(run: WorkflowPackRunDescriptor) -> bool:
    return run.review_required and run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW


def is_workflow_pack_run_historical(run: WorkflowPackRunDescriptor) -> bool:
    return (
        run.superseded_by_run_id is not None
        or run.review_state
        in {WorkflowPackRunReviewState.REVISED, WorkflowPackRunReviewState.SUPERSEDED}
        or run.runtime_state is WorkflowPackRunRuntimeState.SUPERSEDED
    )


def has_workflow_pack_run_partial_output(run: WorkflowPackRunDescriptor) -> bool:
    return run.runtime_state in {
        WorkflowPackRunRuntimeState.FAILED,
        WorkflowPackRunRuntimeState.EXPIRED,
    } and bool(run.output_preview.strip() or run.structured_output_keys)


def _resolve_workflow_pack_supportability_status(
    *,
    runtime_state: WorkflowPackRunRuntimeState,
    review_state: WorkflowPackRunReviewState,
    review_required: bool,
    artifact_ref_count: int,
    evidence_descriptor_count: int,
    superseded_by_run_id: str | None,
) -> WorkflowPackRunSupportabilityStatus:
    if (
        superseded_by_run_id is not None
        or review_state
        in {WorkflowPackRunReviewState.REVISED, WorkflowPackRunReviewState.SUPERSEDED}
        or runtime_state is WorkflowPackRunRuntimeState.SUPERSEDED
    ):
        return WorkflowPackRunSupportabilityStatus.HISTORICAL
    if (
        runtime_state in {WorkflowPackRunRuntimeState.FAILED, WorkflowPackRunRuntimeState.EXPIRED}
        or review_state
        in {WorkflowPackRunReviewState.REJECTED, WorkflowPackRunReviewState.ABANDONED}
        or (review_required and review_state is WorkflowPackRunReviewState.AWAITING_REVIEW)
        or artifact_ref_count == 0
        or evidence_descriptor_count == 0
    ):
        return WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
    return WorkflowPackRunSupportabilityStatus.READY
