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
    assert provider_request.prompt_version == "foundation.explain.v1"
    assert provider_request.output_label == "EXPLANATION_ONLY"
    assert provider_request.safety_mode == "documented_only"
    assert provider_request.redaction_posture == "MINIMIZATION_REQUIRED"
    assert provider_request.context_summary == "Explain rebalance outcome"
    assert provider_request.context_payload == {"status": "BLOCKED", "rule_count": 3}
    assert provider_request.source_refs == ["lotus-manage:run:reb_001"]
