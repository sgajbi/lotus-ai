from __future__ import annotations

from dataclasses import dataclass

from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.providers import ProviderExecutionResponse
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
_REMOVED_STRUCTURED_OUTPUT_KEYS = {
    "caller_app",
    "context_summary",
    "source_refs",
}
_BLOCKED_STRUCTURED_OUTPUT_KEYS = {
    "context_payload",
    "raw_context",
    "raw_source_refs",
}


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


def resolve_safety_execution_outcome(
    policy: ResolvedSafetyPolicy,
    *,
    safety_mode: str | None = None,
) -> SafetyExecutionOutcome:
    resolved_safety_mode = safety_mode or resolve_runtime_mode_config().safety_mode
    if resolved_safety_mode == "runtime_enforced":
        return _build_enforced_safety_outcome(policy, safety_mode=resolved_safety_mode)
    return SafetyExecutionOutcome(
        safety_mode=resolved_safety_mode,
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
                control_id="structured_output_key_minimization",
                execution_state=SafetyControlExecutionState.DOCUMENTED_ONLY,
                summary=(
                    "Deterministic structured-output key minimization runs only under "
                    "runtime-enforced safety mode."
                ),
            ),
            SafetyControlExecutionResult(
                control_id="runtime_redaction_engine",
                execution_state=SafetyControlExecutionState.DOCUMENTED_ONLY,
                summary=(
                    "A runtime redaction engine (content screening for PII, account and card "
                    "identifiers) is not implemented; redaction remains documented-only."
                ),
            ),
        ],
        decision_summary=(
            "Safety posture is typed and reviewable, but content redaction remains "
            "documented-only: no runtime redaction engine exists."
        ),
    )


def apply_safety_enforcement(
    *,
    policy: ResolvedSafetyPolicy,
    provider_execution: ProviderExecutionResponse,
) -> tuple[ProviderExecutionResponse, SafetyExecutionOutcome]:
    if resolve_runtime_mode_config().safety_mode != "runtime_enforced":
        return provider_execution, resolve_safety_execution_outcome(policy)

    if policy.redaction_posture == RedactionPosture.DOCUMENTED_ONLY:
        return (
            provider_execution,
            _build_enforced_safety_outcome(
                policy,
                safety_mode=resolve_runtime_mode_config().safety_mode,
                disposition=SafetyExecutionDisposition.ENFORCED_PASSTHROUGH,
                decision_summary=(
                    "Runtime safety enforcement is active and no redaction was required for "
                    "this output label."
                ),
            ),
        )

    blocked_keys = sorted(
        key
        for key in provider_execution.structured_output.keys()
        if key in _BLOCKED_STRUCTURED_OUTPUT_KEYS
    )
    if blocked_keys:
        blocked_outcome = _build_enforced_safety_outcome(
            policy,
            safety_mode=resolve_runtime_mode_config().safety_mode,
            disposition=SafetyExecutionDisposition.BLOCKED,
            decision_summary=(
                "Runtime safety enforcement blocked execution because the provider payload "
                f"contained unsupported raw context echo fields: {', '.join(blocked_keys)}."
            ),
        )
        return (
            provider_execution.model_copy(
                update={
                    "message": "Task output blocked by deterministic runtime safety enforcement.",
                    "structured_output": {
                        "safety_blocked": True,
                        "blocked_reason": blocked_outcome.decision_summary,
                        "output_label": policy.output_label.value,
                    },
                }
            ),
            blocked_outcome,
        )

    sanitized_output = {
        key: value
        for key, value in provider_execution.structured_output.items()
        if key not in _REMOVED_STRUCTURED_OUTPUT_KEYS
    }
    sanitized_message = _sanitize_message(provider_execution.message)

    output_changed = sanitized_output != provider_execution.structured_output
    message_changed = sanitized_message != provider_execution.message
    if sanitized_message.strip():
        disposition = (
            SafetyExecutionDisposition.ENFORCED_REDACTED
            if output_changed or message_changed
            else SafetyExecutionDisposition.ENFORCED_PASSTHROUGH
        )
        summary = (
            "Runtime safety enforcement applied deterministic minimization to the task result."
            if disposition == SafetyExecutionDisposition.ENFORCED_REDACTED
            else "Runtime safety enforcement ran and did not need to modify the task result."
        )
        outcome = _build_enforced_safety_outcome(
            policy,
            safety_mode=resolve_runtime_mode_config().safety_mode,
            disposition=disposition,
            decision_summary=summary,
        )
        return (
            provider_execution.model_copy(
                update={
                    "message": sanitized_message,
                    "structured_output": sanitized_output,
                }
            ),
            outcome,
        )

    degraded_output = dict(sanitized_output)
    degraded_output["safety_fallback"] = "GENERIC_MINIMIZED_MESSAGE"
    degraded_message = "Safety-minimized output generated for bounded Lotus task execution."
    degraded_outcome = _build_enforced_safety_outcome(
        policy,
        safety_mode=resolve_runtime_mode_config().safety_mode,
        disposition=SafetyExecutionDisposition.DEGRADED,
        decision_summary=(
            "Runtime safety enforcement produced a conservative fallback message because the "
            "original result preview could not be preserved safely."
        ),
    )
    return (
        provider_execution.model_copy(
            update={
                "message": degraded_message,
                "structured_output": degraded_output,
            }
        ),
        degraded_outcome,
    )


def _build_enforced_safety_outcome(
    policy: ResolvedSafetyPolicy,
    *,
    safety_mode: str,
    disposition: SafetyExecutionDisposition = SafetyExecutionDisposition.ENFORCED_PASSTHROUGH,
    decision_summary: str | None = None,
) -> SafetyExecutionOutcome:
    return SafetyExecutionOutcome(
        safety_mode=safety_mode,
        output_label=policy.output_label.value,
        redaction_posture=policy.redaction_posture,
        disposition=disposition,
        # No runtime redaction engine exists (issue #150): what runs under
        # runtime-enforced mode is deterministic key minimization and
        # identity-echo truncation, reported under its own honest control id.
        runtime_redaction_active=False,
        enforced_controls=[
            *_ENFORCED_CONTROL_IDS,
            "structured_output_key_minimization",
        ],
        control_results=[
            SafetyControlExecutionResult(
                control_id="context_minimization",
                execution_state=SafetyControlExecutionState.ENFORCED,
                summary="Context minimization is enforced through deterministic output rules.",
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
                control_id="structured_output_key_minimization",
                execution_state=SafetyControlExecutionState.ENFORCED,
                summary=(
                    "Deterministic structured-output key minimization and identity-echo "
                    "truncation ran for this execution."
                ),
            ),
            SafetyControlExecutionResult(
                control_id="runtime_redaction_engine",
                execution_state=SafetyControlExecutionState.DOCUMENTED_ONLY,
                summary=(
                    "A runtime redaction engine (content screening for PII, account and card "
                    "identifiers) is not implemented; redaction remains documented-only."
                ),
            ),
        ],
        decision_summary=decision_summary
        or "Runtime safety enforcement is active for this execution.",
    )


def _sanitize_message(message: str) -> str:
    requested_by_marker = " requested by "
    if requested_by_marker not in message:
        return message
    prefix, _, suffix = message.partition(requested_by_marker)
    if "." in suffix:
        _, _, trailing = suffix.partition(".")
        return f"{prefix.strip()}.{trailing}".strip()
    return prefix.strip()
