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
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionType,
)


def test_record_workflow_pack_run_for_advisor_brief_task_execution() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-001",
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
    assert recorded.pack_id == "advisor_brief.pack"
    assert recorded.registration_ref == "advisor_brief.pack@v1"
    assert recorded.task_id == "explain.v1"
    assert recorded.review_required is True
    assert recorded.review_state.value == "AWAITING_REVIEW"
    assert recorded.runtime_state.value == "COMPLETED"
    assert recorded.workflow_authority_owner == "lotus-gateway"
    assert "advisor_brief_status" in recorded.structured_output_keys
    assert any(
        descriptor.evidence_type == "task_contract" for descriptor in recorded.evidence_descriptors
    )


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
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-003",
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

    catalog = build_workflow_pack_run_catalog()

    assert catalog.run_store_mode == "memory"
    assert catalog.run_count == 1
    assert catalog.awaiting_review_count == 1
    assert catalog.completed_count == 1
    detail = build_workflow_pack_run_detail(run_id=recorded.run_id)
    assert detail.run.run_id == recorded.run_id
    assert detail.events[0].event_type.value == "RUN_RECORDED"


def test_workflow_pack_run_detail_rejects_unknown_run() -> None:
    try:
        build_workflow_pack_run_detail(run_id="unknown-run")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack run lookup to fail")


def test_accept_review_action_updates_review_state_and_records_history() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-004",
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
            caller_app="lotus-gateway",
            reviewed_by="banker.sg.001",
            reason="Advisor brief reviewed and accepted for bounded downstream use.",
        ),
    )

    assert review_response.run.review_state.value == "ACCEPTED"
    assert review_response.events[0].event_type.value == "REVIEW_STATE_UPDATED"
    assert "bounded downstream use" in review_response.events[0].message
    assert any("bounded downstream use" in line for line in review_response.summary)
    detail = build_workflow_pack_run_detail(run_id=recorded.run_id)
    assert detail.run.review_state.value == "ACCEPTED"
    assert any(event.review_state.value == "ACCEPTED" for event in detail.events)


def test_revise_review_action_links_replacement_run_and_preserves_lineage() -> None:
    original_context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-005",
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
        context=original_context, response=original_response
    )
    assert original_run is not None

    revised_context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-006",
            ),
            context=TaskContextEnvelope(
                summary="Draft revised advisor brief from source performance facts.",
                payload={
                    "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.55,
                        "benchmark_return_pct": 7.93,
                        "active_return_pct": -6.38,
                    },
                    "supportability": [{"key": "portfolio_context", "value": "ready"}],
                },
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
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
    assert review_response.run.superseded_by_run_id == revised_run.run_id
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
