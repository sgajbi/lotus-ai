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
from app.services.workflow_pack_run_consumer_view import build_workflow_pack_run_consumer_view
from app.services.workflow_pack_run_ledger import record_workflow_pack_run_for_task_execution


def test_workflow_pack_run_consumer_view_groups_runtime_review_and_provenance() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-pack-run-consumer-001",
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
    assert consumer_view.lineage.workflow_authority_owner == "lotus-gateway"
    assert "advisor_brief_status" in consumer_view.provenance.structured_output_keys
    assert any(
        descriptor.evidence_type == "task_contract"
        for descriptor in consumer_view.provenance.evidence_descriptors
    )


def test_workflow_pack_run_consumer_view_rejects_unknown_run() -> None:
    try:
        build_workflow_pack_run_consumer_view(run_id="unknown-run")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack run consumer view lookup to fail")
