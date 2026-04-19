from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDescriptor,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)


def resolve_workflow_pack_run_supportability_status(
    run: WorkflowPackRunDescriptor,
) -> WorkflowPackRunSupportabilityStatus:
    if is_workflow_pack_run_historical(run):
        return WorkflowPackRunSupportabilityStatus.HISTORICAL
    if (
        run.runtime_state in {WorkflowPackRunRuntimeState.FAILED, WorkflowPackRunRuntimeState.EXPIRED}
        or run.review_state in {WorkflowPackRunReviewState.REJECTED, WorkflowPackRunReviewState.ABANDONED}
        or is_workflow_pack_run_review_pending(run)
        or len(run.artifact_refs) == 0
        or len(run.evidence_descriptors) == 0
    ):
        return WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
    return WorkflowPackRunSupportabilityStatus.READY


def is_workflow_pack_run_review_pending(run: WorkflowPackRunDescriptor) -> bool:
    return run.review_required and run.review_state is WorkflowPackRunReviewState.AWAITING_REVIEW


def is_workflow_pack_run_historical(run: WorkflowPackRunDescriptor) -> bool:
    return (
        run.superseded_by_run_id is not None
        or run.review_state in {WorkflowPackRunReviewState.REVISED, WorkflowPackRunReviewState.SUPERSEDED}
        or run.runtime_state is WorkflowPackRunRuntimeState.SUPERSEDED
    )


def has_workflow_pack_run_partial_output(run: WorkflowPackRunDescriptor) -> bool:
    return run.runtime_state in {
        WorkflowPackRunRuntimeState.FAILED,
        WorkflowPackRunRuntimeState.EXPIRED,
    } and bool(run.output_preview.strip() or run.structured_output_keys)
