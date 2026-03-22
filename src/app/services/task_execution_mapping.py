from __future__ import annotations

from typing import TYPE_CHECKING

from app.contracts.audit import AuditRecordResponse
from app.contracts.tasks import (
    TaskAuditMetadata,
    TaskExecutionResponse,
    TaskExecutionResult,
    TaskExecutionStatus,
)
from app.services.execution_evidence import build_execution_evidence
from app.services.task_execution_models import ResolvedTaskExecution, TaskExecutionContext

if TYPE_CHECKING:
    pass


def map_task_execution_response(
    *,
    resolved: ResolvedTaskExecution,
) -> TaskExecutionResponse:
    context = resolved.context
    evidence = build_execution_evidence(
        request=context.request,
        capability=context.capability,
        prompt=context.prompt,
        provider_execution=resolved.provider_execution,
        safety_outcome=context.safety_outcome,
    )
    return TaskExecutionResponse(
        status=TaskExecutionStatus.COMPLETED,
        task_id=context.capability.task_id,
        category=context.capability.category,
        output_label=context.capability.output_label,
        result=TaskExecutionResult(
            message=resolved.provider_execution.message,
            structured_output=build_task_result_payload(
                context=context,
                resolved=resolved,
            ),
        ),
        evidence=evidence,
        audit=TaskAuditMetadata(
            request_id=context.request_id,
            task_id=context.capability.task_id,
            output_label=context.capability.output_label,
            prompt_version=context.prompt.prompt_version,
            provider_mode=resolved.provider_execution.provider_mode,
            safety=context.safety_outcome,
            generated_at=context.generated_at,
            stubbed=resolved.provider_execution.stubbed,
        ),
    )


def build_task_result_payload(
    *,
    context: TaskExecutionContext,
    resolved: ResolvedTaskExecution,
) -> dict[str, object]:
    return {
        **resolved.provider_execution.structured_output,
        "input_mode": context.request.input_mode,
        "caller_app": context.request.caller.caller_app,
    }


def map_audit_record(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
) -> AuditRecordResponse:
    return AuditRecordResponse(
        request_id=response.audit.request_id,
        task_id=response.task_id,
        category=response.category,
        output_label=response.output_label,
        caller_app=context.request.caller.caller_app,
        correlation_id=context.request.caller.correlation_id,
        prompt_version=response.audit.prompt_version,
        provider_mode=response.audit.provider_mode,
        safety_mode=response.audit.safety.safety_mode,
        redaction_posture=response.audit.safety.redaction_posture,
        enforced_safety_controls=response.audit.safety.enforced_controls,
        generated_at=response.audit.generated_at,
        stubbed=response.audit.stubbed,
        context_summary=context.request.context.summary,
        context_keys=sorted(context.request.context.payload.keys()),
        source_refs=context.request.context.source_refs,
        result_preview=response.result.message,
        structured_output=response.result.structured_output,
        evidence=response.evidence,
    )
