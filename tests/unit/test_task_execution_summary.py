from app.services.task_execution_summary import build_task_execution_summary
from app.services.task_executor import execute_task
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)


def test_build_task_execution_summary_counts_stubbed_and_retrieval_backed_runs() -> None:
    execute_task(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-summary-1",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Explain rebalance outcome",
                payload={"status": "BLOCKED"},
                source_refs=[],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )
    execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-summary-2",
                tenant_id="tenant-sg-001",
            ),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=[],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    summary = build_task_execution_summary(limit=20)

    assert summary.sampled_record_count >= 2
    assert summary.stubbed_execution_count >= 1
    assert summary.non_stubbed_execution_count >= 1
    assert any(sample.category.value == "explain" for sample in summary.categories)
    assert any(sample.category.value == "knowledge_search" for sample in summary.categories)
    assert any(sample.provider_mode == "catalog_only" for sample in summary.provider_modes)
    assert any(sample.provider_mode != "catalog_only" for sample in summary.provider_modes)
