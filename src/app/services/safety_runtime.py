from __future__ import annotations

from app.contracts.safety import (
    RedactionPosture,
    SafetyExecutionOutcome,
)
from app.contracts.tasks import OutputLabel
from app.services.safety_enforcement import (
    resolve_safety_execution_outcome,
    resolve_safety_policy_for_output,
)


def build_safety_execution_outcome(output_label: OutputLabel) -> SafetyExecutionOutcome:
    policy = resolve_safety_policy_for_output(output_label)
    return resolve_safety_execution_outcome(policy)


def build_safety_execution_outcome_from_record(
    *,
    safety_mode: str,
    output_label: OutputLabel,
    redaction_posture: RedactionPosture,
    enforced_controls: list[str],
) -> SafetyExecutionOutcome:
    policy = resolve_safety_policy_for_output(output_label)
    outcome = resolve_safety_execution_outcome(policy, safety_mode=safety_mode)
    return outcome.model_copy(
        update={
            "redaction_posture": redaction_posture,
            "enforced_controls": list(enforced_controls),
        }
    )
