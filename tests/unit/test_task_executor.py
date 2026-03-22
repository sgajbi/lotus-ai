from fastapi import HTTPException

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
    assert response.audit.stubbed is True
    assert response.audit.prompt_version == "foundation.explain.v1"


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
