from datetime import datetime

from app.contracts.tasks import OutputLabel
from app.services.task_execution_mapping import map_audit_record, map_task_execution_response
from app.services.task_execution_pipeline import resolve_task_execution, validate_task_request
from tests.unit.test_task_executor import _request


def test_map_task_execution_response_preserves_runtime_context_fields() -> None:
    context = validate_task_request(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )
    resolved = resolve_task_execution(context=context)

    response = map_task_execution_response(resolved=resolved)

    assert response.task_id == "explain.v1"
    assert response.result.structured_output["caller_app"] == "lotus-manage"
    assert response.result.structured_output["input_mode"] == "STRUCTURED_CONTEXT"
    assert response.audit.request_id == context.request_id
    assert response.audit.prompt_version == "foundation.explain.v1"
    assert response.audit.prompt_selection.prompt_version == "foundation.explain.v1"
    assert response.audit.prompt_selection.active_prompt_version == "foundation.explain.v1"
    assert response.audit.prompt_selection.latest_control_event is None
    assert datetime.fromisoformat(response.audit.generated_at.replace("Z", "+00:00")) >= (
        datetime.fromisoformat(context.execution_started_at.replace("Z", "+00:00"))
    )


def test_map_audit_record_preserves_sorted_context_keys() -> None:
    context = validate_task_request(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )
    resolved = resolve_task_execution(context=context)
    response = map_task_execution_response(resolved=resolved)

    audit_record = map_audit_record(context=context, response=response)

    assert audit_record.request_id == context.request_id
    assert audit_record.category == response.category
    assert audit_record.output_label == response.output_label
    assert audit_record.caller_app == "lotus-manage"
    assert audit_record.requested_by is None
    assert audit_record.tenant_id == "tenant-sg-001"
    assert audit_record.context_keys == ["rule_count", "status"]
    # A short message persists whole; the cap only bites past the preview bound.
    assert audit_record.result_preview == response.result.message
    assert audit_record.prompt_selection.prompt_version == "foundation.explain.v1"
    assert audit_record.evidence == response.evidence


def test_map_audit_record_caps_result_preview_at_persistence() -> None:
    """Minimisation (issue #158, S4): the caller received the full message in
    the task response; the audit row keeps a bounded preview with an explicit
    truncation marker, never a second full copy."""

    context = validate_task_request(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )
    resolved = resolve_task_execution(context=context)
    response = map_task_execution_response(resolved=resolved)
    long_message = "x" * 2000
    response = response.model_copy(
        update={"result": response.result.model_copy(update={"message": long_message})}
    )

    audit_record = map_audit_record(context=context, response=response)

    assert len(audit_record.result_preview) < len(long_message)
    assert audit_record.result_preview.startswith("x" * 512)
    assert audit_record.result_preview.endswith("[truncated 1488 of 2000 chars]")


def test_map_audit_record_preserves_full_caller_identity() -> None:
    request = _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    request.caller.requested_by = "ops.user@lotus"
    request.caller.tenant_id = "tenant-sg-001"
    context = validate_task_request(request)
    resolved = resolve_task_execution(context=context)
    response = map_task_execution_response(resolved=resolved)

    audit_record = map_audit_record(context=context, response=response)

    assert audit_record.requested_by == "ops.user@lotus"
    assert audit_record.tenant_id == "tenant-sg-001"


def test_map_audit_record_carries_governed_model_identity() -> None:
    context = validate_task_request(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )
    resolved = resolve_task_execution(context=context)
    # Simulate the provider gateway's catalogue stamping (#175 S2a); the
    # mapping layer must carry the governed identity through untouched.
    resolved.provider_execution.model_version = "gpt-5.4-2026-05-01"
    resolved.provider_execution.model_catalogue_entry_id = "text.openai:gpt-5.4-2026-05-01"
    resolved.provider_execution.model_revision_pinned = True

    response = map_task_execution_response(resolved=resolved)

    assert response.audit.model_version == "gpt-5.4-2026-05-01"
    assert response.audit.model_catalogue_entry_id == "text.openai:gpt-5.4-2026-05-01"
    assert response.audit.model_revision_pinned is True

    audit_record = map_audit_record(context=context, response=response)

    assert audit_record.model_version == "gpt-5.4-2026-05-01"
    assert audit_record.model_catalogue_entry_id == "text.openai:gpt-5.4-2026-05-01"
    assert audit_record.model_revision_pinned is True

    # The stub pipeline recorded a real fixed-policy routing decision; the
    # mapping layer must carry it into the durable audit record untouched.
    assert response.audit.routing_decision is not None
    assert audit_record.routing_decision == response.audit.routing_decision
    assert audit_record.routing_decision.selected_provider_id == "text.stub"
    assert audit_record.routing_decision.policy_id == "fixed_configured_mode"


def test_failure_detail_and_category_inference_fallbacks() -> None:
    from fastapi import HTTPException

    from app.services.task_execution_pipeline import (
        _http_exception_detail,
        _infer_failure_category,
    )

    assert (
        _http_exception_detail(HTTPException(status_code=503, detail={"not": "a-string"}))
        == "Workflow-pack execution failed before lotus-ai could produce a completed task result."
    )
    assert _http_exception_detail(HTTPException(status_code=503, detail="  padded  ")) == "padded"
    assert _infer_failure_category("QUOTA_EXCEEDED: limit reached") == "QUOTA_EXCEEDED"
    assert _infer_failure_category("not a known prefix") is None
