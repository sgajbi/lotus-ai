from __future__ import annotations

from app.contracts.providers import ProviderExecutionRequest
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.task_execution_models import TaskExecutionContext


def build_provider_execution_request(
    *,
    context: TaskExecutionContext,
) -> ProviderExecutionRequest:
    config = resolve_provider_execution_config()
    return ProviderExecutionRequest(
        task_id=context.capability.task_id,
        caller_app=context.request.caller.caller_app,
        requested_by=context.request.caller.requested_by,
        tenant_id=context.request.caller.tenant_id,
        prompt_version=context.prompt.prompt_version,
        system_instructions=context.prompt.system_instructions,
        output_contract_notes=context.prompt.output_contract_notes,
        output_label=context.capability.output_label.value,
        safety_mode=context.safety_outcome.safety_mode,
        redaction_posture=context.safety_outcome.redaction_posture.value,
        context_summary=context.request.context.summary,
        context_payload=context.request.context.payload,
        source_refs=context.request.context.source_refs,
        timeout_ms=config.timeout_ms,
        retry_limit=config.retry_limit,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        seed=config.seed,
    )
