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
