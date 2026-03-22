from __future__ import annotations

from app.contracts.providers import ProviderExecutionRequest
from app.services.provider_execution_controls import build_provider_execution_controls
from app.services.task_execution_models import TaskExecutionContext


def build_provider_execution_request(
    *,
    context: TaskExecutionContext,
) -> ProviderExecutionRequest:
    controls = build_provider_execution_controls()
    return ProviderExecutionRequest(
        task_id=context.capability.task_id,
        caller_app=context.request.caller.caller_app,
        prompt_version=context.prompt.prompt_version,
        output_label=context.capability.output_label.value,
        safety_mode=context.safety_outcome.safety_mode,
        redaction_posture=context.safety_outcome.redaction_posture.value,
        context_summary=context.request.context.summary,
        context_payload=context.request.context.payload,
        source_refs=context.request.context.source_refs,
        timeout_ms=controls.timeout_ms,
        retry_limit=controls.retry_limit,
        max_output_tokens=controls.max_output_tokens,
    )
