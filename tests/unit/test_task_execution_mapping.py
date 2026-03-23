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
    assert audit_record.tenant_id is None
    assert audit_record.context_keys == ["rule_count", "status"]
    assert audit_record.result_preview == response.result.message
    assert audit_record.prompt_selection.prompt_version == "foundation.explain.v1"
    assert audit_record.evidence == response.evidence


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
