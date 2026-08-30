from app.contracts.tasks import OutputLabel
from app.services.safety_runtime import build_safety_execution_outcome


def test_safety_runtime_builds_execution_outcome_for_output_label() -> None:
    outcome = build_safety_execution_outcome(OutputLabel.EXPLANATION_ONLY)

    assert outcome.safety_mode == "documented_only"
    assert outcome.output_label == "EXPLANATION_ONLY"
    assert outcome.redaction_posture == "MINIMIZATION_REQUIRED"
    assert outcome.disposition == "DOCUMENTED_ONLY"
    # Issue #150 slice 2: the redaction engine enforces in every mode.
    assert outcome.runtime_redaction_active is True
    assert outcome.enforced_controls == [
        "response_labeling",
        "correlation_and_audit",
        "runtime_redaction_engine",
    ]
    assert outcome.control_results[0].control_id == "context_minimization"
    assert outcome.control_results[-1].control_id == "runtime_redaction_engine"
    assert "redaction engine screens generated content" in outcome.decision_summary
