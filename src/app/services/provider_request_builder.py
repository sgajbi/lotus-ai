from __future__ import annotations

from typing import TYPE_CHECKING

from app.contracts.providers import ProviderExecutionRequest

if TYPE_CHECKING:
    from app.services.task_execution_pipeline import TaskExecutionContext


def build_provider_execution_request(
    *,
    context: TaskExecutionContext,
) -> ProviderExecutionRequest:
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
    )
