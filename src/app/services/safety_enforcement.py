from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.contracts.providers import ProviderExecutionResponse
from app.contracts.safety import (
    RedactionFindingDescriptor,
    RedactionPosture,
    SafetyControlExecutionResult,
    SafetyControlExecutionState,
    SafetyExecutionDisposition,
    SafetyExecutionOutcome,
)
from app.contracts.tasks import OutputLabel
from app.services.redaction_engine import (
    REDACTION_MODE_ENFORCE,
    build_redaction_findings,
    redact_structured_output,
    redact_text,
)
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.services.safety_policy import get_redaction_posture_for_label
from app.services.structured_logging import log_event

_logger = logging.getLogger(__name__)

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
        runtime_redaction_available=True,
    )


def _is_redaction_enforcing() -> bool:
    return resolve_runtime_mode_config().redaction_mode == REDACTION_MODE_ENFORCE


def _redaction_engine_control_state() -> SafetyControlExecutionState:
    if _is_redaction_enforcing():
        return SafetyControlExecutionState.ENFORCED
    return SafetyControlExecutionState.OBSERVED


def _redaction_engine_summary() -> str:
    if _is_redaction_enforcing():
        return (
            "Deterministic redaction engine screened generated content for sensitive "
            "identifiers before persistence and egress."
        )
    return (
        "Deterministic redaction engine observed generated content; findings are "
        "counted but content is not modified in observe mode."
    )


def redact_content_for_audit(
    text: str,
    *,
    client_identifiers: Iterable[str] = (),
    allowlisted_types: Iterable[str] = (),
) -> tuple[str, list[RedactionFindingDescriptor]]:
    """Redact one text field bound for persistence (fail-closed in enforce mode)."""

    try:
        result = redact_text(
            text,
            client_identifiers=client_identifiers,
            allowlisted_types=allowlisted_types,
        )
    except Exception as exc:
        _handle_engine_failure(exc)
        return text, []
    findings = build_redaction_findings(result.counts)
    if _is_redaction_enforcing():
        return result.text, findings
    return text, findings


def _handle_engine_failure(exc: Exception) -> None:
    if _is_redaction_enforcing():
        # Fail closed: releasing unscreened content in enforce mode would be
        # a silent compliance failure; withholding it is recoverable.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SAFETY_REDACTION_UNAVAILABLE: the deterministic redaction engine failed; "
                "output is withheld rather than released unscreened."
            ),
        ) from exc
    log_event(
        _logger,
        "problem_response",
        error_code="SAFETY_REDACTION_UNAVAILABLE",
        detail="Redaction engine failed in observe mode; content passed through uncounted.",
    )


def merge_redaction_findings(
    *groups: list[RedactionFindingDescriptor],
) -> list[RedactionFindingDescriptor]:
    counts: dict[str, int] = {}
    for group in groups:
        for finding in group:
            counts[finding.finding_type] = counts.get(finding.finding_type, 0) + finding.count
    return build_redaction_findings(counts)


def _apply_redaction_engine(
    provider_execution: ProviderExecutionResponse,
    *,
    client_identifiers: Iterable[str],
    allowlisted_types: Iterable[str],
) -> tuple[ProviderExecutionResponse, list[RedactionFindingDescriptor]]:
    try:
        message_result = redact_text(
            provider_execution.message,
            client_identifiers=client_identifiers,
            allowlisted_types=allowlisted_types,
        )
        structured_result, structured_counts = redact_structured_output(
            provider_execution.structured_output,
            client_identifiers=client_identifiers,
            allowlisted_types=allowlisted_types,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _handle_engine_failure(exc)
        return provider_execution, []
    findings = merge_redaction_findings(
        build_redaction_findings(message_result.counts),
        build_redaction_findings(structured_counts),
    )
    if not _is_redaction_enforcing() or not findings:
        return provider_execution, findings
    return (
        provider_execution.model_copy(
            update={
                "message": message_result.text,
                "structured_output": structured_result,
            }
        ),
        findings,
    )


def resolve_safety_execution_outcome(
    policy: ResolvedSafetyPolicy,
    *,
    safety_mode: str | None = None,
    redactions: list[RedactionFindingDescriptor] | None = None,
) -> SafetyExecutionOutcome:
    resolved_safety_mode = safety_mode or resolve_runtime_mode_config().safety_mode
    if resolved_safety_mode == "runtime_enforced":
        return _build_enforced_safety_outcome(
            policy, safety_mode=resolved_safety_mode, redactions=redactions
        )
    return SafetyExecutionOutcome(
        safety_mode=resolved_safety_mode,
        output_label=policy.output_label.value,
        redaction_posture=policy.redaction_posture,
        disposition=SafetyExecutionDisposition.DOCUMENTED_ONLY,
        runtime_redaction_active=_is_redaction_enforcing(),
        redactions=redactions or [],
        enforced_controls=(
            [*_ENFORCED_CONTROL_IDS, "runtime_redaction_engine"]
            if _is_redaction_enforcing()
            else list(_ENFORCED_CONTROL_IDS)
        ),
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
                execution_state=_redaction_engine_control_state(),
                summary=_redaction_engine_summary(),
            ),
        ],
        decision_summary=(
            "Safety posture is documented-only for this execution; the deterministic "
            "redaction engine screens generated content independently of safety mode."
        ),
    )


def apply_safety_enforcement(
    *,
    policy: ResolvedSafetyPolicy,
    provider_execution: ProviderExecutionResponse,
    client_identifiers: Iterable[str] = (),
    redaction_allowlisted_types: Iterable[str] = (),
) -> tuple[ProviderExecutionResponse, SafetyExecutionOutcome]:
    provider_execution, redactions = _apply_redaction_engine(
        provider_execution,
        client_identifiers=client_identifiers,
        allowlisted_types=redaction_allowlisted_types,
    )
    if resolve_runtime_mode_config().safety_mode != "runtime_enforced":
        return provider_execution, resolve_safety_execution_outcome(policy, redactions=redactions)

    if policy.redaction_posture == RedactionPosture.DOCUMENTED_ONLY:
        return (
            provider_execution,
            _build_enforced_safety_outcome(
                policy,
                safety_mode=resolve_runtime_mode_config().safety_mode,
                disposition=SafetyExecutionDisposition.ENFORCED_PASSTHROUGH,
                redactions=redactions,
                decision_summary=(
                    "Runtime safety enforcement is active and no minimization was required "
                    "for this output label."
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
            redactions=redactions,
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
            if output_changed or message_changed or (redactions and _is_redaction_enforcing())
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
            redactions=redactions,
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
        redactions=redactions,
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
    redactions: list[RedactionFindingDescriptor] | None = None,
    decision_summary: str | None = None,
) -> SafetyExecutionOutcome:
    return SafetyExecutionOutcome(
        safety_mode=safety_mode,
        output_label=policy.output_label.value,
        redaction_posture=policy.redaction_posture,
        disposition=disposition,
        runtime_redaction_active=_is_redaction_enforcing(),
        redactions=redactions or [],
        enforced_controls=[
            *_ENFORCED_CONTROL_IDS,
            "structured_output_key_minimization",
            *(["runtime_redaction_engine"] if _is_redaction_enforcing() else []),
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
                execution_state=_redaction_engine_control_state(),
                summary=_redaction_engine_summary(),
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
