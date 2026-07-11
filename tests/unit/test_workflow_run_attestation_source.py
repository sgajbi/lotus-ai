from dataclasses import asdict

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.task_execution_models import TaskExecutionContext
from app.services.task_execution_pipeline import build_task_execution_response, resolve_task_execution
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_run_attestation_source import capture_workflow_run_attestation_source
from tests.support.workflow_pack_fixtures import (
    idea_explanation_workflow_pack_execution_request_json,
)


def _idea_execution() -> tuple[
    TaskExecutionContext,
    TaskExecutionResponse,
    WorkflowPackRegistrationDescriptor,
]:
    request_json = idea_explanation_workflow_pack_execution_request_json(
        correlation_id="corr-attestation-source-001"
    )
    request = TaskExecutionRequest.model_validate(request_json["task_request"])
    context = build_task_execution_context(request)
    response = build_task_execution_response(resolved=resolve_task_execution(context=context))
    registration = get_workflow_pack_registration(pack_id="idea_explanation.pack", version="v1")
    assert registration is not None
    return context, response, registration


def test_idea_workflow_attestation_source_captures_governed_stub_posture() -> None:
    context, response, registration = _idea_execution()

    source = capture_workflow_run_attestation_source(
        run_id="workflow-run-001",
        context=context,
        response=response,
        registration=registration,
    )

    assert source.evaluator_id == "idea-explanation-guardrails"
    assert source.evaluator_policy_version == "idea-explanation-policy.v1"
    assert source.provider_id == "text.stub"
    assert source.model_id == "deterministic-stub"
    assert source.model_version == "stub.v1"
    assert source.model_risk_status == "test_only"
    assert all(
        len(value) == 64
        for value in (
            source.input_evidence_sha256,
            source.output_content_sha256,
            source.replay_nonce,
        )
    )


def test_workflow_attestation_source_is_deterministic_and_stores_no_business_payload() -> None:
    context, response, registration = _idea_execution()

    first = capture_workflow_run_attestation_source(
        run_id="workflow-run-001",
        context=context,
        response=response,
        registration=registration,
    )
    repeated = capture_workflow_run_attestation_source(
        run_id="workflow-run-001",
        context=context,
        response=response,
        registration=registration,
    )
    different_run = capture_workflow_run_attestation_source(
        run_id="workflow-run-002",
        context=context,
        response=response,
        registration=registration,
    )

    assert repeated == first
    assert different_run.input_evidence_sha256 == first.input_evidence_sha256
    assert different_run.output_content_sha256 == first.output_content_sha256
    assert different_run.replay_nonce != first.replay_nonce
    persisted_values = str(asdict(first))
    assert "idea_high_cash_001" not in persisted_values
    assert "PB_SG_GLOBAL_BAL_001" not in persisted_values
