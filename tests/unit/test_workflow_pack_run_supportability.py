from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.services.workflow_pack_run_supportability import (
    has_workflow_pack_run_partial_output,
    is_workflow_pack_run_historical,
    is_workflow_pack_run_review_pending,
    resolve_workflow_pack_run_record_supportability_status,
    resolve_workflow_pack_run_supportability_status,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from tests.support.workflow_pack_run_builders import build_workflow_pack_run_descriptor


def test_resolve_workflow_pack_run_supportability_status_marks_review_pending_run_action_required() -> (
    None
):
    run = build_workflow_pack_run_descriptor(
        run_id="run-review-pending",
        review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
    )

    assert is_workflow_pack_run_review_pending(run) is True
    assert resolve_workflow_pack_run_supportability_status(run) is (
        WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED
    )


def test_resolve_workflow_pack_run_supportability_status_marks_superseded_run_historical() -> None:
    run = build_workflow_pack_run_descriptor(
        run_id="run-historical",
        review_state=WorkflowPackRunReviewState.SUPERSEDED,
        superseded_by_run_id="run-replacement",
    )

    assert is_workflow_pack_run_historical(run) is True
    assert resolve_workflow_pack_run_supportability_status(run) is (
        WorkflowPackRunSupportabilityStatus.HISTORICAL
    )


def test_resolve_workflow_pack_run_supportability_status_marks_accepted_run_ready() -> None:
    run = build_workflow_pack_run_descriptor(
        run_id="run-ready",
        review_state=WorkflowPackRunReviewState.ACCEPTED,
        evidence_descriptors_count=1,
        artifact_refs_count=1,
    )

    assert resolve_workflow_pack_run_supportability_status(run) is (
        WorkflowPackRunSupportabilityStatus.READY
    )


def test_has_workflow_pack_run_partial_output_requires_terminal_failure_or_expiry() -> None:
    failed = build_workflow_pack_run_descriptor(
        run_id="run-failed",
        runtime_state=WorkflowPackRunRuntimeState.FAILED,
    )
    accepted = build_workflow_pack_run_descriptor(
        run_id="run-accepted",
        review_state=WorkflowPackRunReviewState.ACCEPTED,
    )

    assert has_workflow_pack_run_partial_output(failed) is True
    assert has_workflow_pack_run_partial_output(accepted) is False


def test_resolve_workflow_pack_run_record_supportability_status_marks_reviewed_record_ready() -> None:
    source_descriptor = build_workflow_pack_run_descriptor(
        run_id="run-record-ready-source",
        review_state=WorkflowPackRunReviewState.ACCEPTED,
        evidence_descriptors_count=1,
        artifact_refs_count=1,
    )
    record = WorkflowPackRunRecord(
        run_id="run-record-ready",
        pack_id="advisor_brief.pack",
        pack_family="advisor_brief",
        pack_version="v1",
        registration_ref="advisor_brief.pack@v1",
        task_id="explain.v1",
        request_id="req-run-record-ready",
        caller_app="lotus-gateway",
        correlation_id="corr-run-record-ready",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
        workflow_authority_owner="lotus-gateway",
        runtime_state=WorkflowPackRunRuntimeState.COMPLETED.value,
        review_state=WorkflowPackRunReviewState.ACCEPTED.value,
        review_required=True,
        provider_mode="catalog_only",
        stubbed=True,
        output_preview="preview",
        structured_output_keys=["advisor_brief_status"],
        evidence_descriptors=source_descriptor.evidence_descriptors,
        artifact_refs=source_descriptor.artifact_refs,
        supersedes_run_id=None,
        superseded_by_run_id=None,
        created_at="2026-04-19T10:00:00Z",
        completed_at="2026-04-19T10:00:00Z",
        last_updated_at="2026-04-19T10:00:00Z",
    )

    assert resolve_workflow_pack_run_record_supportability_status(record) is (
        WorkflowPackRunSupportabilityStatus.READY
    )
