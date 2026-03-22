from __future__ import annotations

from app.config import settings
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import OutputLabel
from app.services.safety_policy import get_redaction_posture_for_label

_ENFORCED_CONTROL_IDS = [
    "response_labeling",
    "correlation_and_audit",
]


def build_safety_execution_outcome(output_label: OutputLabel) -> SafetyExecutionOutcome:
    return SafetyExecutionOutcome(
        safety_mode=settings.safety_mode,
        output_label=output_label.value,
        redaction_posture=get_redaction_posture_for_label(output_label),
        enforced_controls=list(_ENFORCED_CONTROL_IDS),
    )
