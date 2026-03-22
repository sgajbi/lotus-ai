from app.contracts.tasks import OutputLabel
from app.services.safety_runtime import build_safety_execution_outcome


def test_safety_runtime_builds_execution_outcome_for_output_label() -> None:
    outcome = build_safety_execution_outcome(OutputLabel.EXPLANATION_ONLY)

    assert outcome.safety_mode == "documented_only"
    assert outcome.output_label == "EXPLANATION_ONLY"
    assert outcome.redaction_posture == "MINIMIZATION_REQUIRED"
    assert outcome.enforced_controls == ["response_labeling", "correlation_and_audit"]
