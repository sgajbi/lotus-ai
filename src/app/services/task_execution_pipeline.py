from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.services.audit_store import get_audit_store
from app.services.knowledge_answer_execution import execute_knowledge_answer
from app.services.knowledge_search_execution import execute_knowledge_search
from app.services.provider_request_builder import build_provider_execution_request
from app.services.safety_enforcement import (
    apply_safety_enforcement,
    resolve_safety_policy_for_output,
)
from app.services.task_execution_context_builder import build_task_execution_context
from app.services.task_execution_mapping import map_audit_record, map_task_execution_response
from app.services.provider_gateway import execute_text_generation
from app.services.task_execution_models import ResolvedTaskExecution, TaskExecutionContext
from app.contracts.tasks import TaskCategory


def validate_task_request(request: TaskExecutionRequest) -> TaskExecutionContext:
    return build_task_execution_context(request)


def resolve_task_execution(
    *,
    context: TaskExecutionContext,
) -> ResolvedTaskExecution:
    if context.capability.category == TaskCategory.KNOWLEDGE_SEARCH:
        provider_execution = execute_knowledge_search(context=context)
    elif context.capability.category == TaskCategory.KNOWLEDGE_ANSWER:
        provider_execution = execute_knowledge_answer(context=context)
    else:
        provider_execution = execute_text_generation(
            build_provider_execution_request(context=context)
        )
    try:
        safe_provider_execution, safety_outcome = apply_safety_enforcement(
            policy=resolve_safety_policy_for_output(context.capability.output_label),
            provider_execution=provider_execution,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return ResolvedTaskExecution(
        context=context,
        provider_execution=safe_provider_execution,
        safety_outcome=safety_outcome,
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
