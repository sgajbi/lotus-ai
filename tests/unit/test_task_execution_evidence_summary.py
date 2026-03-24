from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.task_execution_evidence_summary import build_task_execution_evidence_summary
from app.services.task_executor import execute_task


def test_build_task_execution_evidence_summary_tracks_citations_and_answer_modes() -> None:
    execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-evidence-1",
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
    execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-evidence-2",
                tenant_id="tenant-sg-001",
            ),
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
            caller=CallerMetadata(
                caller_app="lotus-manage",
                correlation_id="corr-evidence-3",
                tenant_id="tenant-sg-001",
            ),
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

    summary = build_task_execution_evidence_summary(limit=20)

    assert summary.sampled_record_count >= 3
    assert summary.citation_bearing_execution_count >= 3
    assert summary.citation_backed_answer_count >= 1
    assert summary.refused_answer_count >= 1
    assert any(sample.answer_mode == "CITATION_BACKED" for sample in summary.answer_modes)
    assert any(
        sample.answer_mode == "REFUSED_INSUFFICIENT_SUPPORT" for sample in summary.answer_modes
    )
    assert any(sample.evidence_type == "retrieval_posture" for sample in summary.evidence_types)
