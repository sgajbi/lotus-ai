from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.task_executor import execute_task
from app.services.task_retrieval_execution_summary import build_task_retrieval_execution_summary


def test_build_task_retrieval_execution_summary_tracks_sources_and_refusals() -> None:
    execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-rsum-1"),
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
    execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-rsum-2"),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
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
    execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-rsum-3"),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
                payload={
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=[],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    summary = build_task_retrieval_execution_summary(limit=20)

    assert summary.sampled_record_count >= 3
    assert summary.retrieval_execution_count >= 3
    assert summary.knowledge_search_execution_count >= 1
    assert summary.knowledge_answer_execution_count >= 2
    assert summary.refused_answer_count >= 1
    assert any(sample.task_id == "knowledge_search.v1" for sample in summary.tasks)
    assert any(sample.task_id == "knowledge_answer.v1" for sample in summary.tasks)
    assert any(sample.retrieval_status == "READY" for sample in summary.retrieval_statuses)
    assert any(sample.source_id == "lotus-platform-rfcs" for sample in summary.sources)
    assert any(sample.answer_mode == "CITATION_BACKED" for sample in summary.answer_modes)
    assert any(
        sample.answer_mode == "REFUSED_INSUFFICIENT_SUPPORT" for sample in summary.answer_modes
    )
