from __future__ import annotations

from app.config import settings
from app.contracts.safety import (
    RedactionPosture,
    SafetyControlDescriptor,
    SafetyControlStatus,
    SafetyPolicyResponse,
    TaskSafetyDescriptor,
)
from app.contracts.tasks import OutputLabel
from app.services.capability_catalog import build_capability_catalog


def build_safety_policy() -> SafetyPolicyResponse:
    catalog = build_capability_catalog()
    return SafetyPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        safety_mode=settings.safety_mode,
        controls=[
            SafetyControlDescriptor(
                control_id="context_minimization",
                status=SafetyControlStatus.DOCUMENTED,
                description=(
                    "Calling applications must send only the minimum structured context required "
                    "for the bounded task."
                ),
            ),
            SafetyControlDescriptor(
                control_id="response_labeling",
                status=SafetyControlStatus.ENFORCED,
                description=(
                    "Every task response carries an explicit output label that downstream systems "
                    "must honor."
                ),
            ),
            SafetyControlDescriptor(
                control_id="correlation_and_audit",
                status=SafetyControlStatus.ENFORCED,
                description=(
                    "Every task execution must retain correlation metadata and audit evidence."
                ),
            ),
            SafetyControlDescriptor(
                control_id="runtime_redaction_engine",
                status=SafetyControlStatus.DOCUMENTED,
                description=(
                    "Role-aware redaction remains documented but is not yet enforced in the "
                    "foundation phase."
                ),
            ),
        ],
        task_policies=[
            _build_task_safety_descriptor(task.task_id, task.output_label) for task in catalog.tasks
        ],
    )


def _build_task_safety_descriptor(task_id: str, output_label: OutputLabel) -> TaskSafetyDescriptor:
    return TaskSafetyDescriptor(
        task_id=task_id,
        output_label=output_label,
        redaction_posture=_redaction_posture_for_label(output_label),
        response_labeling_required=True,
        intended_use_notes=_intended_use_notes_for_label(output_label),
    )


def _redaction_posture_for_label(output_label: OutputLabel) -> RedactionPosture:
    if output_label in {OutputLabel.EXPLANATION_ONLY, OutputLabel.RETRIEVAL_ANSWER}:
        return RedactionPosture.MINIMIZATION_REQUIRED
    return RedactionPosture.DOCUMENTED_ONLY


def _intended_use_notes_for_label(output_label: OutputLabel) -> str:
    if output_label == OutputLabel.EXPLANATION_ONLY:
        return "Use only for explanatory assistance; never as authoritative business truth."
    if output_label == OutputLabel.DRAFT:
        return "Use as draft content that requires human and domain-system review."
    if output_label == OutputLabel.CLASSIFICATION:
        return "Use only within caller-approved label boundaries."
    return "Use only with explicit source attribution and caller-side review."
