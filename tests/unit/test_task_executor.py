from typing import cast

from fastapi import HTTPException
from pytest_mock import MockerFixture

from app.contracts.audit import AuditRecordResponse
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.config import settings
from app.services.task_executor import execute_task


def _request(
    task_id: str, expected_output_label: OutputLabel | None = None
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_id=task_id,
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-123"),
        context=TaskContextEnvelope(
            summary="Explain rebalance outcome",
            payload={"status": "BLOCKED", "rule_count": 3},
            source_refs=["lotus-manage:run:reb_001"],
        ),
        expected_output_label=expected_output_label,
    )


def test_execute_task_returns_stubbed_completed_response() -> None:
    response = execute_task(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert response.status == "COMPLETED"
    assert response.task_id == "explain.v1"
    assert response.result.structured_output["phase"] == "foundation"
    assert response.result.structured_output["provider_id"] == "text.stub"
    assert response.result.structured_output["context_keys"] == ["rule_count", "status"]
    assert response.result.structured_output["output_label"] == "EXPLANATION_ONLY"
    assert response.result.structured_output["redaction_posture"] == "MINIMIZATION_REQUIRED"
    assert response.audit.stubbed is True
    assert response.audit.prompt_version == "foundation.explain.v1"
    assert response.audit.safety.safety_mode == "documented_only"
    assert response.audit.safety.redaction_posture == "MINIMIZATION_REQUIRED"
    assert response.audit.safety.enforced_controls == [
        "response_labeling",
        "correlation_and_audit",
    ]
    assert len(response.evidence.descriptors) == 5
    assert response.evidence.descriptors[0].evidence_type == "task_contract"
    assert response.evidence.descriptors[1].evidence_type == "prompt_selection"


def test_execute_task_rejects_unknown_task() -> None:
    try:
        execute_task(_request("unknown.v1"))
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "Unknown lotus-ai task_id" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown task")


def test_execute_task_rejects_output_label_mismatch() -> None:
    try:
        execute_task(_request("explain.v1", expected_output_label=OutputLabel.DRAFT))
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Expected output label does not match task configuration" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for output label mismatch")


def test_execute_task_persists_sorted_audit_context_keys(mocker: MockerFixture) -> None:
    audit_store = mocker.Mock()
    mocker.patch("app.services.task_execution_pipeline.get_audit_store", return_value=audit_store)

    execute_task(
        TaskExecutionRequest(
            task_id="explain.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-123"),
            context=TaskContextEnvelope(
                summary="Explain rebalance outcome",
                payload={"zeta": 1, "alpha": 2},
                source_refs=["lotus-manage:run:reb_001"],
            ),
            expected_output_label=OutputLabel.EXPLANATION_ONLY,
        )
    )

    audit_record = cast(AuditRecordResponse, audit_store.save.call_args.args[0])
    assert audit_record.context_keys == ["alpha", "zeta"]
    assert audit_record.caller_app == "lotus-manage"
    assert audit_record.correlation_id == "corr-123"
    assert audit_record.prompt_version == "foundation.explain.v1"


def test_execute_task_runs_bounded_knowledge_search() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ks-123"),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-search:001"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.task_id == "knowledge_search.v1"
    assert response.output_label == OutputLabel.RETRIEVAL_ANSWER
    assert response.audit.stubbed is False
    assert response.audit.prompt_version == "foundation.knowledge_search.v1"
    assert response.audit.provider_mode == "catalog_only"
    assert response.result.structured_output["provider_id"] == "retrieval.catalog"
    assert response.result.structured_output["catalog_only"] is True
    assert response.result.structured_output["query"] == "shared ai platform service"
    assert response.result.structured_output["hit_count"] >= 1
    assert response.result.structured_output["citation_count"] >= 1
    assert response.result.structured_output["support_score"] >= 0.5
    assert response.result.structured_output["citations"][0]["source_id"] == "lotus-platform-rfcs"
    assert response.result.structured_output["hits"][0]["source_id"] == "lotus-platform-rfcs"


def test_execute_task_rejects_invalid_knowledge_search_payload() -> None:
    try:
        execute_task(
            TaskExecutionRequest(
                task_id="knowledge_search.v1",
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ks-124"),
                context=TaskContextEnvelope(
                    summary="Search Lotus knowledge sources",
                    payload={"query": "", "limit": 3},
                    source_refs=[],
                ),
                expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "context.payload.query" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for invalid knowledge-search payload")


def test_execute_task_runs_bounded_knowledge_answer() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ka-123"),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-answer:001"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.task_id == "knowledge_answer.v1"
    assert response.output_label == OutputLabel.RETRIEVAL_ANSWER
    assert response.audit.stubbed is False
    assert response.audit.prompt_version == "foundation.knowledge_answer.v1"
    assert response.audit.provider_mode == "catalog_answer"
    assert response.result.structured_output["provider_id"] == "retrieval.answer"
    assert response.result.structured_output["catalog_only"] is True
    assert response.result.structured_output["hit_count"] >= 1
    assert response.result.structured_output["answer_mode"] == "CITATION_BACKED"
    assert response.result.structured_output["support_score"] >= 0.5
    assert (
        response.result.structured_output["support_assessment"]["meets_support_threshold"] is True
    )
    assert response.result.structured_output["support_assessment"]["refusal_reason"] is None
    assert response.result.structured_output["citations"][0]["source_id"] == "lotus-platform-rfcs"
    assert "Sources: lotus-platform-rfcs" in response.result.message


def test_execute_task_uses_indexed_retrieval_when_enabled() -> None:
    settings.retrieval_mode = "enabled"

    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_search.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ks-indexed"),
            context=TaskContextEnvelope(
                summary="Search Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-search:indexed"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.audit.provider_mode == "indexed_search"
    assert response.result.structured_output["provider_id"] == "retrieval.indexed"
    assert response.result.structured_output["catalog_only"] is False
    assert response.result.structured_output["retrieval_execution_stage"] == "INDEXED_SEARCH"
    assert response.result.structured_output["hits"][0]["document_id"] == "lotus-platform-rfc-0069"


def test_execute_task_runs_indexed_knowledge_answer_when_enabled() -> None:
    settings.retrieval_mode = "enabled"

    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ka-indexed"),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
                payload={
                    "query": "shared ai platform service",
                    "source_ids": ["lotus-platform-rfcs", "lotus-ai-architecture"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-answer:indexed"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.audit.provider_mode == "indexed_answer"
    assert response.result.structured_output["provider_id"] == "retrieval.indexed_answer"
    assert response.result.structured_output["catalog_only"] is False
    assert response.result.structured_output["retrieval_execution_stage"] == "INDEXED_SEARCH"
    assert response.result.structured_output["answer_mode"] == "CITATION_BACKED"
    assert (
        response.result.structured_output["support_assessment"]["meets_support_threshold"] is True
    )
    assert response.result.message.startswith("Based on approved Lotus sources")


def test_execute_task_refuses_low_support_knowledge_answer() -> None:
    response = execute_task(
        TaskExecutionRequest(
            task_id="knowledge_answer.v1",
            input_mode=TaskInputMode.STRUCTURED_CONTEXT,
            caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ka-124"),
            context=TaskContextEnvelope(
                summary="Answer from Lotus knowledge sources",
                payload={
                    "query": "shared migration standards",
                    "source_ids": ["lotus-platform-rfcs"],
                    "limit": 3,
                },
                source_refs=["lotus-manage:knowledge-answer:002"],
            ),
            expected_output_label=OutputLabel.RETRIEVAL_ANSWER,
        )
    )

    assert response.status == "COMPLETED"
    assert response.result.structured_output["answer_mode"] == "REFUSED_INSUFFICIENT_SUPPORT"
    assert response.result.structured_output["support_score"] < 0.75
    assert (
        response.result.structured_output["support_assessment"]["meets_support_threshold"] is False
    )
    assert (
        response.result.structured_output["support_assessment"]["refusal_reason"]
        == "LOW_SUPPORT_SCORE"
    )
    assert "Insufficient support" in response.result.message
