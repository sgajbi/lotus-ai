from app.contracts.safety import SafetyControlStatus
from app.services.safety_policy import build_safety_policy


def test_safety_policy_exposes_controls_and_task_posture() -> None:
    response = build_safety_policy()

    assert response.service == "lotus-ai"
    assert response.safety_mode == "documented_only"
    assert any(control.control_id == "response_labeling" for control in response.controls)
    assert any(control.status == SafetyControlStatus.ENFORCED for control in response.controls)
    assert any(task.task_id == "explain.v1" for task in response.task_policies)
