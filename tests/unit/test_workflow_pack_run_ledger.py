from dataclasses import replace

from fastapi import HTTPException

from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.task_execution_pipeline import (
    build_task_execution_response,
    resolve_task_execution,
)
from app.services.workflow_pack_run_ledger import (
    build_workflow_pack_run_catalog,
    build_workflow_pack_run_detail,
    record_workflow_pack_run_for_task_execution,
)
from app.services.workflow_pack_run_review import apply_workflow_pack_run_review_action
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from tests.support.workflow_pack_fixtures import advisor_brief_task_execution_request


def test_record_workflow_pack_run_for_advisor_brief_task_execution() -> None:
    context = build_task_execution_context(
        advisor_brief_task_execution_request(correlation_id="corr-pack-run-001")
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))

    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)

    assert recorded is not None
    assert recorded.pack_id == "advisor_brief.pack"
    assert recorded.registration_ref == "advisor_brief.pack@v1"
    assert recorded.task_id == "explain.v1"
    assert recorded.review_required is True
    assert recorded.review_state.value == "AWAITING_REVIEW"
    assert recorded.supportability_status.value == "ACTION_REQUIRED"
    assert [action.value for action in recorded.allowed_review_actions] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]
    assert recorded.runtime_state.value == "COMPLETED"
    assert recorded.workflow_authority_owner == "lotus-gateway"
    assert "advisor_brief_status" in recorded.structured_output_keys
    assert any(
        descriptor.evidence_type == "task_contract" for descriptor in recorded.evidence_descriptors
    )
    assert len(recorded.artifact_refs) == 1
    artifact = recorded.artifact_refs[0]
    assert artifact.domain == "workflow_pack"
    assert artifact.artifact_type == "run_output_summary"
    assert artifact.source_object_kind == "workflow_pack_run"
    assert artifact.source_object_id == recorded.run_id
    assert artifact.retention_posture == "retained_for_review"


def test_record_workflow_pack_run_ignores_non_pack_task_execution() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-pack-run-002",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Explain a generic management workflow state.",
                payload={
                    "status": "BLOCKED",
                    "reason": "Awaiting operator approval",
                },
                source_refs=[],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))

    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)

    assert recorded is None
    assert build_workflow_pack_run_catalog().run_count == 0


def test_workflow_pack_run_catalog_and_detail_expose_recorded_history() -> None:
    context = build_task_execution_context(
        advisor_brief_task_execution_request(correlation_id="corr-pack-run-003")
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    catalog = build_workflow_pack_run_catalog()

    assert catalog.run_store_mode == "memory"
    assert catalog.run_count == 1
    assert catalog.filters_applied == {"limit": 100}
    assert catalog.awaiting_review_count == 1
    assert catalog.completed_count == 1
    assert catalog.ready_count == 0
    assert catalog.action_required_count == 1
    assert catalog.historical_count == 0
    assert "shared run-supportability seam" in catalog.notes[3]
    assert "Phase-1 recorded runs now emit governed workflow-pack artifact refs" in catalog.notes[4]
    assert catalog.runs[0].supportability_status.value == "ACTION_REQUIRED"
    assert catalog.runs[0].review_summary.latest_review_event_at is None
    assert catalog.runs[0].review_summary.latest_review_actor is None
    assert catalog.runs[0].review_summary.review_transition_count == 0
    assert catalog.runs[0].review_summary.has_review_history is False
    detail = build_workflow_pack_run_detail(run_id=recorded.run_id)
    assert detail.run.run_id == recorded.run_id
    assert detail.review.state.value == "AWAITING_REVIEW"
    assert detail.review.latest_review_event_at is None
    assert detail.review.latest_review_actor is None
    assert detail.review.review_transition_count == 0
    assert detail.review.has_review_history is False
    assert detail.provenance.artifact_ref_count == 1
    assert detail.provenance.artifact_types == ["run_output_summary"]
    assert detail.provenance.evidence_descriptor_count >= 1
    assert "task_contract" in detail.provenance.evidence_types
    assert detail.supportability.status.value == "ACTION_REQUIRED"
    assert detail.supportability.review_pending is True
    assert len(detail.run.artifact_refs) == 1
    assert detail.events[0].event_type.value == "RUN_RECORDED"


def test_workflow_pack_run_catalog_filters_by_supportability_and_limit() -> None:
    awaiting_context = build_task_execution_context(
        advisor_brief_task_execution_request(
            correlation_id="corr-pack-run-filter-001",
            caller_app="lotus-gateway",
            tenant_id="tenant-sg-001",
        )
    )
    awaiting_response = build_task_execution_response(
        resolved=resolve_task_execution(context=awaiting_context)
    )
    awaiting_run = record_workflow_pack_run_for_task_execution(
        context=awaiting_context,
        response=awaiting_response,
    )
    assert awaiting_run is not None

    accepted_context = build_task_execution_context(
        advisor_brief_task_execution_request(
            correlation_id="corr-pack-run-filter-002",
            caller_app="lotus-gateway",
            tenant_id="tenant-us-002",
        )
    )
    accepted_response = build_task_execution_response(
        resolved=resolve_task_execution(context=accepted_context)
    )
    accepted_run = record_workflow_pack_run_for_task_execution(
        context=accepted_context,
        response=accepted_response,
    )
    assert accepted_run is not None
    apply_workflow_pack_run_review_action(
        run_id=accepted_run.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.filter",
            reason="Accepted for filter coverage.",
        ),
    )

    filtered_catalog = build_workflow_pack_run_catalog(
        registration_ref="advisor_brief.pack@v1",
        caller_app="lotus-gateway",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
        runtime_state=WorkflowPackRunRuntimeState.COMPLETED,
        review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
        supportability_status=WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        workflow_authority_owner="lotus-gateway",
        limit=1,
    )

    assert filtered_catalog.filters_applied == {
        "limit": 1,
        "registration_ref": "advisor_brief.pack@v1",
        "caller_app": "lotus-gateway",
        "tenant_id": "tenant-sg-001",
        "workflow_surface": "advisor-brief-workspace",
        "runtime_state": "COMPLETED",
        "review_state": "AWAITING_REVIEW",
        "supportability_status": "ACTION_REQUIRED",
        "workflow_authority_owner": "lotus-gateway",
    }
    assert filtered_catalog.run_count == 1
    assert [run.run_id for run in filtered_catalog.runs] == [awaiting_run.run_id]
    assert filtered_catalog.runs[0].caller_app == "lotus-gateway"
    assert filtered_catalog.runs[0].tenant_id == "tenant-sg-001"
    assert filtered_catalog.runs[0].workflow_surface == "advisor-brief-workspace"
    assert filtered_catalog.runs[0].supportability_status.value == "ACTION_REQUIRED"
    assert filtered_catalog.awaiting_review_count == 1
    assert filtered_catalog.completed_count == 1
    assert filtered_catalog.ready_count == 0
    assert filtered_catalog.action_required_count == 1
    assert filtered_catalog.historical_count == 0


def test_workflow_pack_run_detail_rejects_unknown_run() -> None:
    try:
        build_workflow_pack_run_detail(run_id="unknown-run")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack run lookup to fail")


def test_accept_review_action_updates_review_state_and_records_history() -> None:
    context = build_task_execution_context(
        advisor_brief_task_execution_request(correlation_id="corr-pack-run-004")
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    review_response = apply_workflow_pack_run_review_action(
        run_id=recorded.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.001",
            reason="Advisor brief reviewed and accepted for bounded downstream use.",
        ),
    )

    assert review_response.run.review_state.value == "ACCEPTED"
    assert [action.value for action in review_response.run.allowed_review_actions] == ["SUPERSEDE"]
    assert review_response.events[0].event_type.value == "REVIEW_STATE_UPDATED"
    assert "bounded downstream use" in review_response.events[0].message
    assert any("bounded downstream use" in line for line in review_response.summary)
    catalog = build_workflow_pack_run_catalog()
    assert catalog.runs[0].review_summary.latest_review_event_at is not None
    assert catalog.runs[0].review_summary.latest_review_actor == "review:banker.sg.001"
    assert catalog.runs[0].review_summary.review_transition_count == 1
    assert catalog.runs[0].review_summary.has_review_history is True
    detail = build_workflow_pack_run_detail(run_id=recorded.run_id)
    assert detail.provenance.artifact_ref_count == 1
    assert "task_contract" in detail.provenance.evidence_types
    assert detail.run.review_state.value == "ACCEPTED"
    assert detail.review.state.value == "ACCEPTED"
    assert detail.review.latest_review_event_at is not None
    assert detail.review.latest_review_actor == "review:banker.sg.001"
    assert detail.review.review_transition_count == 1
    assert detail.review.has_review_history is True
    assert any(event.review_state.value == "ACCEPTED" for event in detail.events)


def test_revise_review_action_links_replacement_run_and_preserves_lineage() -> None:
    original_context = build_task_execution_context(
        advisor_brief_task_execution_request(correlation_id="corr-pack-run-005")
    )
    original_response = build_task_execution_response(
        resolved=resolve_task_execution(context=original_context)
    )
    original_run = record_workflow_pack_run_for_task_execution(
        context=original_context, response=original_response
    )
    assert original_run is not None

    revised_context = build_task_execution_context(
        advisor_brief_task_execution_request(
            correlation_id="corr-pack-run-006",
            summary="Draft revised advisor brief from source performance facts.",
            portfolio_return_pct=1.55,
            active_return_pct=-6.38,
        )
    )
    revised_response = build_task_execution_response(
        resolved=resolve_task_execution(context=revised_context)
    )
    revised_run = record_workflow_pack_run_for_task_execution(
        context=revised_context, response=revised_response
    )
    assert revised_run is not None

    review_response = apply_workflow_pack_run_review_action(
        run_id=original_run.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.REVISE,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.002",
            reason="Reviewer requested a revised advisor brief draft.",
            replacement_run_id=revised_run.run_id,
        ),
    )

    assert review_response.run.review_state.value == "REVISED"
    assert review_response.run.allowed_review_actions == []
    assert review_response.run.superseded_by_run_id == revised_run.run_id
    assert any(
        f"Replacement lineage now points to `{revised_run.run_id}`" in line
        for line in review_response.summary
    )
    replacement_detail = build_workflow_pack_run_detail(run_id=revised_run.run_id)
    assert replacement_detail.run.supersedes_run_id == original_run.run_id
    assert any(event.event_type.value == "LINEAGE_UPDATED" for event in replacement_detail.events)


def test_review_action_rejects_invalid_transition() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-007",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    apply_workflow_pack_run_review_action(
        run_id=recorded.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.003",
            reason="Initial acceptance.",
        ),
    )

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.REJECT,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.003",
                reason="Second review should not overwrite accepted posture.",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected invalid review-state transition to fail")


def test_review_action_rejects_unauthorized_caller() -> None:
    try:
        apply_workflow_pack_run_review_action(
            run_id="packrun_advisor_brief_pack_missing",
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.ACCEPT,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.004",
                reason="Unknown run should fail before authorization is evaluated.",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack run to fail")

    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-008",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.ACCEPT,
                caller_app="lotus-manage",
                reviewed_by="banker.sg.004",
                reason="Caller mismatch should fail.",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected unauthorized review caller to fail")

    store = get_workflow_pack_run_store()
    stored = store.get_run(run_id=recorded.run_id)
    assert stored is not None
    store.save_run(replace(stored, caller_app="unknown-app"))

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.ACCEPT,
                caller_app="unknown-app",
                reviewed_by="banker.sg.004",
                reason="Unknown original caller should fail even when the run record matches it.",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert (
            exc.detail
            == "Workflow-pack review-state actions are currently limited to the original active registered caller app or a caller authorized for async control-plane actions while downstream review integration remains bounded."
        )
    else:
        raise AssertionError("Expected unknown original review caller to fail")


def test_review_action_allows_operator_caller() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-operator-caller-001",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    review_response = apply_workflow_pack_run_review_action(
        run_id=recorded.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-platform",
            reviewed_by="ops.sg.platform.001",
            reason="Platform operator recorded bounded review acceptance.",
        ),
    )

    assert review_response.run.review_state.value == "ACCEPTED"
    assert review_response.run.allowed_review_actions == [
        WorkflowPackRunReviewActionType.SUPERSEDE
    ]
    assert review_response.events[0].actor == "review:ops.sg.platform.001"


def test_review_action_rejects_replacement_run_for_accept() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-009",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.ACCEPT,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.005",
                reason="Accept should not take replacement lineage.",
                replacement_run_id="packrun_advisor_brief_pack_unused",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("Expected accept action with replacement run id to fail")


def test_review_action_rejects_missing_or_unknown_replacement_run() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-010",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.REVISE,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.006",
                reason="Revise requires a replacement run id.",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("Expected revise without replacement run id to fail")

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.REVISE,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.006",
                reason="Unknown replacement run id should fail.",
                replacement_run_id="packrun_advisor_brief_pack_missing",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown replacement run id to fail")


def test_review_action_rejects_non_reviewable_posture() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-nonreviewable-001",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    recorded = record_workflow_pack_run_for_task_execution(context=context, response=response)
    assert recorded is not None

    store = get_workflow_pack_run_store()
    stored = store.get_run(run_id=recorded.run_id)
    assert stored is not None
    store.save_run(
        replace(
            stored,
            review_required=False,
            review_state=WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED.value,
        )
    )

    try:
        apply_workflow_pack_run_review_action(
            run_id=recorded.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.ACCEPT,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.006b",
                reason="Non-reviewable posture should reject review actions.",
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "not allowed" in exc.detail
    else:
        raise AssertionError("Expected non-reviewable workflow-pack run to reject review action")


def test_review_action_rejects_invalid_replacement_lineage() -> None:
    original_context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-011",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    original_response = build_task_execution_response(
        resolved=resolve_task_execution(context=original_context)
    )
    original_run = record_workflow_pack_run_for_task_execution(
        context=original_context,
        response=original_response,
    )
    assert original_run is not None

    try:
        apply_workflow_pack_run_review_action(
            run_id=original_run.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.REVISE,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.007",
                reason="Self lineage should fail.",
                replacement_run_id=original_run.run_id,
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected self replacement lineage to fail")

    replacement_context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-012",
            ),
            context=TaskContextEnvelope(
                summary="Draft revised advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.35,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.58,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    replacement_response = build_task_execution_response(
        resolved=resolve_task_execution(context=replacement_context)
    )
    replacement_run = record_workflow_pack_run_for_task_execution(
        context=replacement_context,
        response=replacement_response,
    )
    assert replacement_run is not None

    store = get_workflow_pack_run_store()
    replacement_record = store.get_run(run_id=replacement_run.run_id)
    assert replacement_record is not None
    store.save_run(replace(replacement_record, pack_family="different_family"))

    try:
        apply_workflow_pack_run_review_action(
            run_id=original_run.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.REVISE,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.007",
                reason="Cross-family lineage should fail.",
                replacement_run_id=replacement_run.run_id,
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected cross-family replacement lineage to fail")

    store.save_run(
        replace(
            replacement_record,
            supersedes_run_id="packrun_advisor_brief_pack_already_linked",
        )
    )
    try:
        apply_workflow_pack_run_review_action(
            run_id=original_run.run_id,
            request=WorkflowPackRunReviewActionRequest(
                action_type=WorkflowPackRunReviewActionType.REVISE,
                caller_app="lotus-gateway",
                reviewed_by="banker.sg.007",
                reason="Replacement already linked should fail.",
                replacement_run_id=replacement_run.run_id,
            ),
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected already-linked replacement lineage to fail")


def test_review_action_allows_supersede_after_acceptance() -> None:
    original_context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-013",
            ),
            context=TaskContextEnvelope(
                summary="Draft advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.68,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    original_response = build_task_execution_response(
        resolved=resolve_task_execution(context=original_context)
    )
    original_run = record_workflow_pack_run_for_task_execution(
        context=original_context,
        response=original_response,
    )
    assert original_run is not None

    replacement_context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-014",
            ),
            context=TaskContextEnvelope(
                summary="Draft superseding advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.4,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.53,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
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
            action_type=WorkflowPackRunReviewActionType.ACCEPT,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.008",
            reason="Initial accepted draft.",
        ),
    )

    review_response = apply_workflow_pack_run_review_action(
        run_id=original_run.run_id,
        request=WorkflowPackRunReviewActionRequest(
            action_type=WorkflowPackRunReviewActionType.SUPERSEDE,
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.008",
            reason="A newer draft superseded the accepted version.",
            replacement_run_id=replacement_run.run_id,
        ),
    )

    assert review_response.run.review_state.value == "SUPERSEDED"
    assert review_response.run.superseded_by_run_id == replacement_run.run_id
    assert review_response.run.allowed_review_actions == []
