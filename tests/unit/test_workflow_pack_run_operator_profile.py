from dataclasses import replace

from fastapi import HTTPException

from app.contracts.tasks import TaskExecutionRequest
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.task_execution_pipeline import (
    build_task_execution_response,
    resolve_task_execution,
)
from app.services.workflow_pack_run_ledger import record_workflow_pack_run_for_task_execution
from app.services.workflow_pack_run_operator_profile import build_workflow_pack_run_operator_profile
from app.services.workflow_pack_run_review import apply_workflow_pack_run_review_action
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from tests.support.workflow_pack_fixtures import advisor_brief_task_execution_request


def test_workflow_pack_run_operator_profile_reports_review_pending_attention() -> None:
    context = build_task_execution_context(_build_request("corr-pack-run-operator-001"))
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    profile = build_workflow_pack_run_operator_profile(run_id=recorded.run_id)

    assert profile.supportability_status.value == "ACTION_REQUIRED"
    assert profile.review_pending is True
    assert profile.failed is False
    assert profile.expired is False
    assert profile.superseded is False
    assert profile.partial_output_visible is False
    assert profile.provenance.artifact_ref_count == 1
    assert profile.provenance.artifact_types == ["run_output_summary"]
    assert profile.provenance.evidence_descriptor_count >= 1
    assert "task_contract" in profile.provenance.evidence_types
    assert profile.artifact_ref_count == 1
    assert profile.evidence_descriptor_count >= 1
    assert profile.history_event_count == 1
    assert profile.latest_event_type is not None
    assert profile.latest_event_type.value == "RUN_RECORDED"
    assert profile.latest_event_actor == "lotus-ai.workflow-pack-run-ledger"
    assert profile.latest_review_event_at is None
    assert profile.latest_review_actor is None
    assert profile.review_transition_count == 0
    assert profile.event_type_counts == {"RUN_RECORDED": 1}
    assert any(finding.finding_id == "review_pending" for finding in profile.findings)
    assert profile.inspection_surfaces[-1].endswith("/operator-profile")


def test_workflow_pack_run_operator_profile_marks_superseded_run_historical() -> None:
    original_context = build_task_execution_context(_build_request("corr-pack-run-operator-002"))
    original_response = build_task_execution_response(
        resolved=resolve_task_execution(context=original_context)
    )
    original_run = record_workflow_pack_run_for_task_execution(
        context=original_context,
        response=original_response,
    )
    assert original_run is not None

    replacement_context = build_task_execution_context(_build_request("corr-pack-run-operator-003"))
    replacement_response = build_task_execution_response(
        resolved=resolve_task_execution(context=replacement_context)
    )
    replacement_run = record_workflow_pack_run_for_task_execution(
        context=replacement_context,
        response=replacement_response,
    )
    assert replacement_run is not None

    apply_workflow_pack_run_review_action(
        run_id=original_run.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.REVISE,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.operator.001",
            reason="Replacement draft is now the active review candidate.",
            replacement_run_id=replacement_run.run_id,
        ),
    )

    profile = build_workflow_pack_run_operator_profile(run_id=original_run.run_id)

    assert profile.supportability_status.value == "HISTORICAL"
    assert profile.superseded is True
    assert profile.replacement_run_id == replacement_run.run_id
    assert profile.review_state is WorkflowPackRunReviewState.REVISED
    assert profile.latest_event_type is not None
    assert profile.latest_event_type.value == "LINEAGE_UPDATED"
    assert profile.latest_review_event_at is not None
    assert profile.latest_review_actor == "review:banker.sg.operator.001"
    assert profile.review_transition_count == 1
    assert profile.event_type_counts["REVIEW_STATE_UPDATED"] == 1
    assert profile.event_type_counts["LINEAGE_UPDATED"] == 1
    assert any(finding.finding_id == "run_historical" for finding in profile.findings)


def test_workflow_pack_run_operator_profile_historical_note_handles_missing_replacement_run() -> (
    None
):
    context = build_task_execution_context(_build_request("corr-pack-run-operator-005"))
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    store = get_workflow_pack_run_store()
    stored = store.get_run(run_id=recorded.run_id)
    assert stored is not None
    store.save_run(
        replace(
            stored,
            runtime_state=WorkflowPackRunRuntimeState.SUPERSEDED.value,
            review_state=WorkflowPackRunReviewState.SUPERSEDED.value,
            superseded_by_run_id=None,
        )
    )

    profile = build_workflow_pack_run_operator_profile(run_id=recorded.run_id)

    assert profile.supportability_status.value == "HISTORICAL"
    assert profile.superseded is True
    assert "None" not in profile.current_summary_note
    assert "historical review state" in profile.current_summary_note


def test_workflow_pack_run_operator_profile_marks_accepted_run_ready() -> None:
    context = build_task_execution_context(_build_request("corr-pack-run-operator-accepted-001"))
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    apply_workflow_pack_run_review_action(
        run_id=recorded.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.operator.002",
            reason="Draft accepted for bounded downstream composition.",
        ),
    )

    profile = build_workflow_pack_run_operator_profile(run_id=recorded.run_id)

    assert profile.supportability_status.value == "READY"
    assert profile.review_pending is False
    assert profile.failed is False
    assert profile.superseded is False
    assert profile.latest_event_type is not None
    assert profile.latest_event_type.value == "REVIEW_STATE_UPDATED"
    assert profile.latest_review_event_at is not None
    assert profile.latest_review_actor == "review:banker.sg.operator.002"
    assert profile.review_transition_count == 1
    assert profile.event_type_counts["RUN_RECORDED"] == 1
    assert profile.event_type_counts["REVIEW_STATE_UPDATED"] == 1
    assert profile.provenance.artifact_ref_count == 1
    assert "task_contract" in profile.provenance.evidence_types
    assert any(finding.finding_id == "run_ready" for finding in profile.findings)


def test_workflow_pack_run_operator_profile_exposes_failed_partial_output() -> None:
    context = build_task_execution_context(_build_request("corr-pack-run-operator-004"))
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    store = get_workflow_pack_run_store()
    stored = store.get_run(run_id=recorded.run_id)
    assert stored is not None
    store.save_run(
        replace(
            stored,
            runtime_state=WorkflowPackRunRuntimeState.FAILED.value,
            review_state=WorkflowPackRunReviewState.AWAITING_REVIEW.value,
        )
    )

    profile = build_workflow_pack_run_operator_profile(run_id=recorded.run_id)

    assert profile.supportability_status.value == "ACTION_REQUIRED"
    assert profile.failed is True
    assert profile.partial_output_visible is True
    assert profile.latest_event_type is not None
    assert profile.latest_event_type.value == "RUN_RECORDED"
    assert profile.latest_review_event_at is None
    assert profile.latest_review_actor is None
    assert profile.review_transition_count == 0
    assert profile.event_type_counts == {"RUN_RECORDED": 1}
    assert profile.provenance.artifact_ref_count == 1
    assert "task_contract" in profile.provenance.evidence_types
    assert any(finding.finding_id == "runtime_failed" for finding in profile.findings)
    assert any(finding.finding_id == "partial_output_visible" for finding in profile.findings)


def test_workflow_pack_run_operator_profile_rejects_unknown_run() -> None:
    try:
        build_workflow_pack_run_operator_profile(run_id="unknown-run")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack run operator profile lookup to fail")


def _build_request(correlation_id: str) -> TaskExecutionRequest:
    return advisor_brief_task_execution_request(correlation_id=correlation_id)
