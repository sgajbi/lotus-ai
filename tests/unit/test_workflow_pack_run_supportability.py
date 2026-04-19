from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.services.workflow_pack_run_supportability import (
    has_workflow_pack_run_partial_output,
    is_workflow_pack_run_historical,
    is_workflow_pack_run_review_pending,
    resolve_workflow_pack_run_supportability_status,
)
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
