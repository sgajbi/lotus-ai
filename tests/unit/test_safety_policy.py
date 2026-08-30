from app.config import settings
from app.contracts.safety import SafetyControlStatus
from app.services.safety_policy import build_safety_policy


def test_safety_policy_exposes_controls_and_task_posture() -> None:
    response = build_safety_policy()

    assert response.service == "lotus-ai"
    assert response.safety_mode == "documented_only"
    assert any(control.control_id == "response_labeling" for control in response.controls)
    assert any(control.status == SafetyControlStatus.ENFORCED for control in response.controls)
    assert any(task.task_id == "explain.v1" for task in response.task_policies)


def test_safety_policy_reports_runtime_redaction_control_as_enforced_when_activated() -> None:
    settings.safety_mode = "runtime_enforced"

    response = build_safety_policy()
    runtime_redaction = next(
        control for control in response.controls if control.control_id == "runtime_redaction_engine"
    )

    assert response.safety_mode == "runtime_enforced"
    assert runtime_redaction.status == SafetyControlStatus.DOCUMENTED
    minimization = next(
        control
        for control in response.controls
        if control.control_id == "structured_output_key_minimization"
    )
    assert minimization.status == SafetyControlStatus.ENFORCED
    assert "not implemented" in runtime_redaction.description.lower()

    settings.safety_mode = "documented_only"
