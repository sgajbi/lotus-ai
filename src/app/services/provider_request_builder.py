from __future__ import annotations

from typing import Literal

from app.contracts.providers import ProviderExecutionRequest
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.task_execution_models import TaskExecutionContext


def _as_cost_posture(value: str) -> Literal["conservative", "actual_only"]:
    """An unrecognised configured posture falls back to conservative - the
    direction that can only overstate spend, never understate it (issue #232)."""

    return "actual_only" if value == "actual_only" else "conservative"


def build_provider_execution_request(
    *,
    context: TaskExecutionContext,
    output_contract_key: str | None = None,
) -> ProviderExecutionRequest:
    config = resolve_provider_execution_config()
    return ProviderExecutionRequest(
        task_id=context.capability.task_id,
        requirements=context.request.requirements,
        output_contract_key=output_contract_key,
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
        failed_attempt_cost_posture=_as_cost_posture(config.failed_attempt_cost_posture),
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        seed=config.seed,
    )
