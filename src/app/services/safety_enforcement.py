from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.safety import (
    RedactionPosture,
    SafetyControlExecutionResult,
    SafetyControlExecutionState,
    SafetyExecutionDisposition,
    SafetyExecutionOutcome,
)
from app.contracts.tasks import OutputLabel
from app.services.safety_policy import get_redaction_posture_for_label

_ENFORCED_CONTROL_IDS = [
    "response_labeling",
    "correlation_and_audit",
]


@dataclass(frozen=True)
class ResolvedSafetyPolicy:
    output_label: OutputLabel
    redaction_posture: RedactionPosture
    runtime_redaction_available: bool


def resolve_safety_policy_for_output(output_label: OutputLabel) -> ResolvedSafetyPolicy:
    return ResolvedSafetyPolicy(
        output_label=output_label,
        redaction_posture=get_redaction_posture_for_label(output_label),
        runtime_redaction_available=False,
    )


def resolve_safety_execution_outcome(policy: ResolvedSafetyPolicy) -> SafetyExecutionOutcome:
    return SafetyExecutionOutcome(
        safety_mode=settings.safety_mode,
        output_label=policy.output_label.value,
        redaction_posture=policy.redaction_posture,
        disposition=SafetyExecutionDisposition.DOCUMENTED_ONLY,
        runtime_redaction_active=False,
        enforced_controls=list(_ENFORCED_CONTROL_IDS),
        control_results=[
            SafetyControlExecutionResult(
                control_id="context_minimization",
                execution_state=SafetyControlExecutionState.DOCUMENTED_ONLY,
                summary=(
                    "Context minimization remains a caller-side documented control in the current "
                    "phase."
                ),
            ),
            SafetyControlExecutionResult(
                control_id="response_labeling",
                execution_state=SafetyControlExecutionState.ENFORCED,
                summary="Output labeling is enforced on every task execution.",
            ),
            SafetyControlExecutionResult(
                control_id="correlation_and_audit",
                execution_state=SafetyControlExecutionState.ENFORCED,
                summary="Correlation metadata and audit capture are enforced on every execution.",
            ),
            SafetyControlExecutionResult(
                control_id="runtime_redaction_engine",
                execution_state=SafetyControlExecutionState.DOCUMENTED_ONLY,
                summary=(
                    "Runtime redaction is typed and inspectable but not yet active in the current "
                    "slice."
                ),
            ),
        ],
        decision_summary=(
            "Safety posture is typed and reviewable, but runtime redaction remains "
            "documented-only in the current slice."
        ),
    )
