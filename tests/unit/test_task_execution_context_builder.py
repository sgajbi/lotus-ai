from app.contracts.tasks import OutputLabel
from app.services.task_execution_context_builder import build_task_execution_context
from tests.unit.test_task_executor import _request


def test_build_task_execution_context_resolves_runtime_fields() -> None:
    context = build_task_execution_context(
        _request("explain.v1", expected_output_label=OutputLabel.EXPLANATION_ONLY)
    )

    assert context.request.task_id == "explain.v1"
    assert context.capability.task_id == "explain.v1"
    assert context.prompt.prompt_version == "foundation.explain.v1"
    assert context.safety_outcome.safety_mode == "documented_only"
    assert context.safety_outcome.redaction_posture == "MINIMIZATION_REQUIRED"
    assert context.safety_outcome.disposition == "DOCUMENTED_ONLY"
    assert context.safety_outcome.runtime_redaction_active is False
    assert context.request_id.startswith("air_")
    assert context.generated_at.endswith("+00:00")
