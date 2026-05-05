from fastapi import HTTPException

from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.services.workflow_pack_execution import (
    execute_workflow_pack,
    validate_workflow_pack_execution_binding,
)
from app.services.workflow_pack_bindings import get_workflow_pack_execution_binding
from tests.support.workflow_pack_fixtures import (
    outcome_review_narrative_workflow_pack_execution_request_json,
)


def test_execute_workflow_pack_rejects_unknown_execution_binding() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        {
            **outcome_review_narrative_workflow_pack_execution_request_json(
                correlation_id="corr-execution-unknown-binding"
            ),
            "pack_id": "unknown.pack",
        }
    )

    try:
        execute_workflow_pack(request)
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Explicit workflow-pack execution is not implemented" in str(exc.detail)
    else:
        raise AssertionError("expected unknown workflow pack to reject execution")


def test_validate_workflow_pack_execution_binding_rejects_wrong_task_id() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        outcome_review_narrative_workflow_pack_execution_request_json(
            correlation_id="corr-execution-wrong-task",
            task_id="summarize.v1",
        )
    )
    binding = get_workflow_pack_execution_binding(
        pack_id="outcome_review_narrative.pack",
        version="v1",
    )
    assert binding is not None

    try:
        validate_workflow_pack_execution_binding(request=request, binding=binding)
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "currently binds to explain.v1 only" in str(exc.detail)
    else:
        raise AssertionError("expected wrong task id to reject workflow-pack execution")


def test_validate_workflow_pack_execution_binding_rejects_missing_payload_sections() -> None:
    request_payload = outcome_review_narrative_workflow_pack_execution_request_json(
        correlation_id="corr-execution-missing-payload"
    )
    task_request = request_payload["task_request"]
    assert isinstance(task_request, dict)
    context = task_request["context"]
    assert isinstance(context, dict)
    context["payload"] = {"ai_evidence_input": {}}

    request = WorkflowPackExecutionRequest.model_validate(request_payload)
    binding = get_workflow_pack_execution_binding(
        pack_id="outcome_review_narrative.pack",
        version="v1",
    )
    assert binding is not None

    try:
        validate_workflow_pack_execution_binding(request=request, binding=binding)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires the bound workflow-pack source payload sections" in str(exc.detail)
    else:
        raise AssertionError("expected missing source payload sections to reject execution")
