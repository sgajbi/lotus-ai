from fastapi import HTTPException

from app.services.task_execution_context_builder import build_task_execution_context
from app.services.task_execution_pipeline import (
    build_task_execution_response,
    resolve_task_execution,
)
from app.services.workflow_pack_run_consumer_view import build_workflow_pack_run_consumer_view
from app.services.workflow_pack_run_ledger import record_workflow_pack_run_for_task_execution
from app.services.workflow_pack_run_review import apply_workflow_pack_run_review_action
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionType,
)
from tests.support.workflow_pack_fixtures import advisor_brief_task_execution_request


def test_workflow_pack_run_consumer_view_groups_runtime_review_and_provenance() -> None:
    context = build_task_execution_context(
        advisor_brief_task_execution_request(correlation_id="corr-pack-run-consumer-001")
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    consumer_view = build_workflow_pack_run_consumer_view(run_id=recorded.run_id)

    assert consumer_view.runtime.state.value == "COMPLETED"
    assert consumer_view.review.state.value == "AWAITING_REVIEW"
    assert [action.value for action in consumer_view.review.allowed_actions] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert consumer_view.review.latest_review_event_at is None
    assert consumer_view.review.latest_review_actor is None
    assert consumer_view.review.review_transition_count == 0
    assert consumer_view.review.has_review_history is False
    assert consumer_view.provenance_summary.artifact_ref_count == 1
    assert consumer_view.provenance_summary.artifact_types == ["run_output_summary"]
    assert consumer_view.provenance_summary.evidence_descriptor_count >= 1
    assert "task_contract" in consumer_view.provenance_summary.evidence_types
    assert consumer_view.supportability.status.value == "ACTION_REQUIRED"
    assert consumer_view.supportability.review_pending is True
    assert consumer_view.supportability.superseded is False
    assert consumer_view.supportability.partial_output_visible is False
    assert "still requires bounded review" in consumer_view.supportability.summary_note
    assert consumer_view.lineage.workflow_authority_owner == "lotus-gateway"
    assert "advisor_brief_status" in consumer_view.provenance.structured_output_keys
    assert any(
        descriptor.evidence_type == "task_contract"
        for descriptor in consumer_view.provenance.evidence_descriptors
    )
    assert len(consumer_view.provenance.artifact_refs) == 1
    assert consumer_view.provenance.artifact_refs[0].domain == "workflow_pack"


def test_workflow_pack_run_consumer_view_exposes_latest_review_transition() -> None:
    context = build_task_execution_context(
        advisor_brief_task_execution_request(correlation_id="corr-pack-run-consumer-002")
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    apply_workflow_pack_run_review_action(
        run_id=recorded.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.consumer.001",
            reason="Accepted for consumer-view coverage.",
        ),
    )

    consumer_view = build_workflow_pack_run_consumer_view(run_id=recorded.run_id)

    assert consumer_view.review.state.value == "ACCEPTED"
    assert consumer_view.review.latest_review_event_at is not None
    assert consumer_view.review.latest_review_actor == "review:banker.sg.consumer.001"
    assert consumer_view.review.review_transition_count == 1
    assert consumer_view.review.has_review_history is True
    assert consumer_view.provenance_summary.artifact_ref_count == 1
    assert "task_contract" in consumer_view.provenance_summary.evidence_types


def test_workflow_pack_run_consumer_view_rejects_unknown_run() -> None:
    try:
        build_workflow_pack_run_consumer_view(run_id="unknown-run")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack run consumer view lookup to fail")
