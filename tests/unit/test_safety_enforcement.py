from app.contracts.tasks import OutputLabel
from app.services.safety_enforcement import (
    resolve_safety_execution_outcome,
    resolve_safety_policy_for_output,
)


def test_safety_enforcement_maps_output_labels_to_typed_documented_only_outcomes() -> None:
    explanation_policy = resolve_safety_policy_for_output(OutputLabel.EXPLANATION_ONLY)
    draft_policy = resolve_safety_policy_for_output(OutputLabel.DRAFT)

    assert explanation_policy.redaction_posture == "MINIMIZATION_REQUIRED"
    assert draft_policy.redaction_posture == "DOCUMENTED_ONLY"
    assert explanation_policy.runtime_redaction_available is False
    assert draft_policy.runtime_redaction_available is False

    explanation_outcome = resolve_safety_execution_outcome(explanation_policy)
    draft_outcome = resolve_safety_execution_outcome(draft_policy)

    assert explanation_outcome.disposition == "DOCUMENTED_ONLY"
    assert draft_outcome.disposition == "DOCUMENTED_ONLY"
    assert explanation_outcome.runtime_redaction_active is False
    assert draft_outcome.runtime_redaction_active is False
    assert explanation_outcome.control_results[-1].control_id == "runtime_redaction_engine"
    assert draft_outcome.control_results[-1].execution_state == "DOCUMENTED_ONLY"
