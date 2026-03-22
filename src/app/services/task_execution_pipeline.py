from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.prompts import PromptDescriptor
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import CapabilityDescriptor, TaskExecutionRequest, TaskExecutionResponse
from app.services.audit_store import get_audit_store
from app.services.task_capability_validator import validate_task_capability
from app.services.provider_request_builder import build_provider_execution_request
from app.services.task_execution_mapping import map_audit_record, map_task_execution_response
from app.services.prompt_runtime import resolve_runtime_prompt_or_raise
from app.services.provider_gateway import execute_text_generation
from app.services.safety_runtime import build_safety_execution_outcome


@dataclass(frozen=True)
class TaskExecutionContext:
    request: TaskExecutionRequest
    capability: CapabilityDescriptor
    prompt: PromptDescriptor
    safety_outcome: SafetyExecutionOutcome
    request_id: str
    generated_at: str


@dataclass(frozen=True)
class ResolvedTaskExecution:
    context: TaskExecutionContext
    provider_execution: ProviderExecutionResponse


def validate_task_request(request: TaskExecutionRequest) -> TaskExecutionContext:
    capability = validate_task_capability(request)
    resolved_prompt = resolve_runtime_prompt_or_raise(request.task_id)
    safety_outcome = build_safety_execution_outcome(capability.output_label)
    return TaskExecutionContext(
        request=request,
        capability=capability,
        prompt=resolved_prompt.prompt,
        safety_outcome=safety_outcome,
        request_id=f"air_{uuid4().hex}",
        generated_at=datetime.now(UTC).isoformat(),
    )


def resolve_task_execution(
    *,
    context: TaskExecutionContext,
) -> ResolvedTaskExecution:
    provider_execution = execute_text_generation(
        build_provider_execution_request(context=context)
    )
    return ResolvedTaskExecution(
        context=context,
        provider_execution=provider_execution,
    )


def build_task_execution_response(
    *,
    resolved: ResolvedTaskExecution,
) -> TaskExecutionResponse:
    return map_task_execution_response(resolved=resolved)


def persist_task_execution_audit(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
) -> None:
    get_audit_store().save(map_audit_record(context=context, response=response))
