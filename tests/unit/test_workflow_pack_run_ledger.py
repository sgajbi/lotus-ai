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
