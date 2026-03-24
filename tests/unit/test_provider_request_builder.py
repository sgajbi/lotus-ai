from app.contracts.tasks import OutputLabel
from app.services.provider_request_builder import build_provider_execution_request
from app.services.task_execution_pipeline import validate_task_request
from tests.unit.test_task_executor import _request


def test_build_provider_execution_request_maps_runtime_context_fields() -> None:
    context = validate_task_request(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    provider_request = build_provider_execution_request(context=context)

    assert provider_request.task_id == "explain.v1"
    assert provider_request.caller_app == "lotus-manage"
    assert provider_request.requested_by is None
    assert provider_request.tenant_id == "tenant-sg-001"
    assert provider_request.prompt_version == "foundation.explain.v1"
    assert "Explain structured Lotus domain outputs clearly" in provider_request.system_instructions
    assert "explanation-oriented" in provider_request.output_contract_notes
    assert provider_request.output_label == "EXPLANATION_ONLY"
    assert provider_request.safety_mode == "documented_only"
    assert provider_request.redaction_posture == "MINIMIZATION_REQUIRED"
    assert provider_request.context_summary == "Explain rebalance outcome"
    assert provider_request.context_payload == {"status": "BLOCKED", "rule_count": 3}
    assert provider_request.source_refs == ["lotus-manage:run:reb_001"]
    assert provider_request.timeout_ms == 4000
    assert provider_request.retry_limit == 0
    assert provider_request.max_output_tokens == 512


def test_build_provider_execution_request_maps_optional_caller_identity() -> None:
    request = _request("explain.v1")
    request.caller.requested_by = "ops.user@lotus"
    request.caller.tenant_id = "tenant-sg-001"
    context = validate_task_request(request)

    provider_request = build_provider_execution_request(context=context)

    assert provider_request.requested_by == "ops.user@lotus"
    assert provider_request.tenant_id == "tenant-sg-001"
