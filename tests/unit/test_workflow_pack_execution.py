from fastapi import HTTPException

from app.contracts.workflow_packs import WorkflowPackExecutionRequest
from app.services.workflow_pack_execution import (
    execute_workflow_pack,
    validate_workflow_pack_execution_binding,
)
from app.services.workflow_pack_bindings import get_workflow_pack_execution_binding
from tests.support.workflow_pack_fixtures import (
    dpm_exception_summary_workflow_pack_execution_request_json,
    operations_handoff_summary_workflow_pack_execution_request_json,
    outcome_review_narrative_workflow_pack_execution_request_json,
    pm_quality_summary_workflow_pack_execution_request_json,
    proof_pack_pm_memo_workflow_pack_execution_request_json,
    wave_pm_memo_workflow_pack_execution_request_json,
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


def test_execute_workflow_pack_records_review_gated_proof_pack_pm_memo() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        proof_pack_pm_memo_workflow_pack_execution_request_json(
            correlation_id="corr-execution-proof-pack-memo"
        )
    )

    response = execute_workflow_pack(request)

    assert response.execution.status.value == "COMPLETED"
    assert response.workflow_pack_run.pack_id == "dpm_pm_memo.pack"
    assert response.workflow_pack_run.workflow_authority_owner == "lotus-manage"
    assert response.execution.result.structured_output["workflow_pack_family"] == "dpm_pm_memo"
    assert response.execution.result.structured_output["state"] == "REVIEW_REQUIRED"
    assert response.execution.result.structured_output["scope"] == "support_only"
    assert (
        response.execution.result.structured_output["proof_pack_content_hash"]
        == "sha256:proof-pack-001"
    )


def test_execute_workflow_pack_records_proof_pack_portfolio_memory_lineage() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        proof_pack_pm_memo_workflow_pack_execution_request_json(
            correlation_id="corr-execution-proof-pack-memory",
            include_portfolio_memory_context=True,
        )
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert structured_output["portfolio_memory_status"] == "supplied"
    assert structured_output["portfolio_memory_content_hash"] == (
        "sha256:portfolio-memory-context-001"
    )
    assert structured_output["portfolio_memory_event_ref_count"] == 2
    assert structured_output["portfolio_memory_event_types"] == [
        "OUTCOME_REVIEW_CREATED",
        "PROOF_PACK_CREATED",
    ]


def test_validate_workflow_pack_execution_binding_runs_proof_pack_guardrails() -> None:
    request_payload = proof_pack_pm_memo_workflow_pack_execution_request_json(
        correlation_id="corr-execution-proof-pack-memo-guardrail",
        requested_outputs=["pm_memo", "client_message"],
    )
    request = WorkflowPackExecutionRequest.model_validate(request_payload)
    binding = get_workflow_pack_execution_binding(
        pack_id="dpm_pm_memo.pack",
        version="v1",
    )
    assert binding is not None

    try:
        validate_workflow_pack_execution_binding(request=request, binding=binding)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden memo outputs requested: client_message" in str(exc.detail)
    else:
        raise AssertionError("expected proof-pack guardrails to reject forbidden memo output")


def test_execute_workflow_pack_records_outcome_review_portfolio_memory_lineage() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        outcome_review_narrative_workflow_pack_execution_request_json(
            correlation_id="corr-execution-outcome-memory",
            include_portfolio_memory_context=True,
        )
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert structured_output["portfolio_memory_status"] == "supplied"
    assert structured_output["portfolio_memory_content_hash"] == (
        "sha256:portfolio-memory-context-001"
    )
    assert structured_output["portfolio_memory_event_count"] == 2


def test_execute_workflow_pack_records_review_gated_wave_pm_memo() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        wave_pm_memo_workflow_pack_execution_request_json(correlation_id="corr-execution-wave-memo")
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert response.execution.status.value == "COMPLETED"
    assert response.workflow_pack_run.pack_id == "dpm_wave_pm_memo.pack"
    assert response.workflow_pack_run.workflow_authority_owner == "lotus-manage"
    assert structured_output["workflow_pack_family"] == "dpm_wave_pm_memo"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["wave_report_content_hash"] == "sha256:wave-report-input-001"
    assert structured_output["proof_pack_ref_count"] == 1


def test_execute_workflow_pack_records_wave_portfolio_memory_lineage() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        wave_pm_memo_workflow_pack_execution_request_json(
            correlation_id="corr-execution-wave-memory",
            include_portfolio_memory_context=True,
        )
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert structured_output["portfolio_memory_status"] == "supplied"
    assert structured_output["portfolio_memory_content_hash"] == (
        "sha256:portfolio-memory-context-001"
    )
    assert structured_output["portfolio_memory_event_ref_count"] == 2


def test_execute_workflow_pack_records_review_gated_operations_handoff_summary() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        operations_handoff_summary_workflow_pack_execution_request_json(
            correlation_id="corr-execution-operations-handoff-summary"
        )
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert response.execution.status.value == "COMPLETED"
    assert response.workflow_pack_run.pack_id == "dpm_operations_handoff_summary.pack"
    assert response.workflow_pack_run.workflow_authority_owner == "lotus-manage"
    assert structured_output["workflow_pack_family"] == "dpm_operations_handoff_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["wave_report_content_hash"] == "sha256:wave-report-input-001"
    assert structured_output["handoff_ref_count"] == 1
    assert structured_output["external_execution_claimed"] is False


def test_execute_workflow_pack_records_review_gated_dpm_exception_summary() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        dpm_exception_summary_workflow_pack_execution_request_json(
            correlation_id="corr-execution-dpm-exception-summary"
        )
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert response.execution.status.value == "COMPLETED"
    assert response.workflow_pack_run.pack_id == "dpm_exception_summary.pack"
    assert response.workflow_pack_run.workflow_authority_owner == "lotus-manage"
    assert structured_output["workflow_pack_family"] == "dpm_exception_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["exception_summary_content_hash"] == (
        "sha256:dpm-exception-summary-input-001"
    )
    assert structured_output["exception_count"] == 2


def test_validate_workflow_pack_execution_binding_runs_dpm_exception_summary_guardrails() -> None:
    request_payload = dpm_exception_summary_workflow_pack_execution_request_json(
        correlation_id="corr-execution-dpm-exception-summary-guardrail",
        requested_outputs=["exception_summary", "client_message"],
    )
    request = WorkflowPackExecutionRequest.model_validate(request_payload)
    binding = get_workflow_pack_execution_binding(
        pack_id="dpm_exception_summary.pack",
        version="v1",
    )
    assert binding is not None

    try:
        validate_workflow_pack_execution_binding(request=request, binding=binding)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden exception summary outputs requested: client_message" in str(exc.detail)
    else:
        raise AssertionError(
            "expected exception summary guardrails to reject client-message output"
        )


def test_validate_workflow_pack_execution_binding_runs_operations_handoff_guardrails() -> None:
    request_payload = operations_handoff_summary_workflow_pack_execution_request_json(
        correlation_id="corr-execution-operations-handoff-guardrail",
        requested_outputs=["operations_summary", "order_ticket"],
    )
    request = WorkflowPackExecutionRequest.model_validate(request_payload)
    binding = get_workflow_pack_execution_binding(
        pack_id="dpm_operations_handoff_summary.pack",
        version="v1",
    )
    assert binding is not None

    try:
        validate_workflow_pack_execution_binding(request=request, binding=binding)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden operations handoff outputs requested: order_ticket" in str(exc.detail)
    else:
        raise AssertionError("expected operations handoff guardrails to reject order-ticket output")


def test_execute_workflow_pack_records_review_gated_pm_quality_summary() -> None:
    request = WorkflowPackExecutionRequest.model_validate(
        pm_quality_summary_workflow_pack_execution_request_json(
            correlation_id="corr-execution-pm-quality-summary"
        )
    )

    response = execute_workflow_pack(request)

    structured_output = response.execution.result.structured_output
    assert response.execution.status.value == "COMPLETED"
    assert response.workflow_pack_run.pack_id == "pm_quality_summary.pack"
    assert response.workflow_pack_run.workflow_authority_owner == "lotus-manage"
    assert structured_output["workflow_pack_family"] == "pm_quality_summary"
    assert structured_output["state"] == "REVIEW_REQUIRED"
    assert structured_output["scope"] == "support_only"
    assert structured_output["score_run_content_hash"] == "sha256:pm-quality-score-run-001"
    assert structured_output["indicator_result_count"] == 1
    assert "pm_ranking" in structured_output["unsupported_claims"]


def test_validate_workflow_pack_execution_binding_runs_pm_quality_summary_guardrails() -> None:
    request_payload = pm_quality_summary_workflow_pack_execution_request_json(
        correlation_id="corr-execution-pm-quality-summary-guardrail",
        requested_outputs=["score_run_summary", "pm_ranking"],
    )
    request = WorkflowPackExecutionRequest.model_validate(request_payload)
    binding = get_workflow_pack_execution_binding(
        pack_id="pm_quality_summary.pack",
        version="v1",
    )
    assert binding is not None

    try:
        validate_workflow_pack_execution_binding(request=request, binding=binding)
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "Forbidden PM quality summary outputs requested: pm_ranking" in str(exc.detail)
    else:
        raise AssertionError("expected PM quality guardrails to reject PM-ranking output")
