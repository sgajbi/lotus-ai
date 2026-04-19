from app.contracts.tasks import (
    CallerMetadata,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.workflow_pack_bindings import (
    get_workflow_pack_execution_binding,
    resolve_workflow_pack_execution_binding_for_task,
)


def test_get_workflow_pack_execution_binding_returns_phase1_binding() -> None:
    binding = get_workflow_pack_execution_binding(pack_id="advisor_brief.pack", version="v1")

    assert binding is not None
    assert binding.task_id == "explain.v1"
    assert binding.default_workflow_surface == "advisor-brief-workspace"


def test_resolve_workflow_pack_execution_binding_for_task_matches_phase1_payload() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-binding-001",
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
            expected_output_label="EXPLANATION_ONLY",
        )
    )

    binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert binding is not None
    assert binding.pack_id == "advisor_brief.pack"
    assert binding.version == "v1"


def test_resolve_workflow_pack_execution_binding_for_task_rejects_nonmatching_payload() -> None:
    context = build_task_execution_context(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-gateway",
                correlation_id="corr-binding-002",
            ),
            context=TaskContextEnvelope(
                summary="Generic explanation payload.",
                payload={"portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"}},
                source_refs=["lotus-gateway:performance-summary:YTD"],
            ),
            expected_output_label="EXPLANATION_ONLY",
        )
    )

    binding = resolve_workflow_pack_execution_binding_for_task(context=context)

    assert binding is None
