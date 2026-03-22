from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.audit import AuditRecordResponse
from app.contracts.prompts import PromptDescriptor
from app.contracts.providers import ProviderExecutionRequest, ProviderExecutionResponse
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import (
    CapabilityDescriptor,
    TaskAuditMetadata,
    TaskExecutionRequest,
    TaskExecutionResponse,
    TaskExecutionResult,
    TaskExecutionStatus,
)
from app.services.audit_store import get_audit_store
from app.services.capability_catalog import get_capability_by_task_id
from app.services.execution_evidence import build_execution_evidence
from app.services.prompt_runtime import resolve_runtime_prompt_or_raise
from app.services.provider_gateway import execute_text_generation
from app.services.safety_runtime import build_safety_execution_outcome


@dataclass(frozen=True)
class ResolvedTaskExecution:
    capability: CapabilityDescriptor
    prompt: PromptDescriptor
    safety_outcome: SafetyExecutionOutcome
    provider_execution: ProviderExecutionResponse
    request_id: str
    generated_at: str


def validate_task_request(request: TaskExecutionRequest) -> CapabilityDescriptor:
    capability = get_capability_by_task_id(request.task_id)
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lotus-ai task_id: {request.task_id}",
        )
    if not capability.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is registered but not enabled in the current phase: {request.task_id}",
        )
    if request.expected_output_label and request.expected_output_label != capability.output_label:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Expected output label does not match task configuration: "
                f"{request.expected_output_label} != {capability.output_label}"
            ),
        )
    return capability


def resolve_task_execution(
    request: TaskExecutionRequest,
    *,
    capability: CapabilityDescriptor,
) -> ResolvedTaskExecution:
    resolved_prompt = resolve_runtime_prompt_or_raise(request.task_id)
    safety_outcome = build_safety_execution_outcome(capability.output_label)
    provider_execution = execute_text_generation(
        ProviderExecutionRequest(
            task_id=capability.task_id,
            caller_app=request.caller.caller_app,
            prompt_version=resolved_prompt.prompt.prompt_version,
            output_label=capability.output_label.value,
            safety_mode=safety_outcome.safety_mode,
            redaction_posture=safety_outcome.redaction_posture.value,
            context_summary=request.context.summary,
            context_payload=request.context.payload,
            source_refs=request.context.source_refs,
        )
    )
    return ResolvedTaskExecution(
        capability=capability,
        prompt=resolved_prompt.prompt,
        safety_outcome=safety_outcome,
        provider_execution=provider_execution,
        request_id=f"air_{uuid4().hex}",
        generated_at=datetime.now(UTC).isoformat(),
    )


def build_task_execution_response(
    request: TaskExecutionRequest,
    *,
    resolved: ResolvedTaskExecution,
) -> TaskExecutionResponse:
    evidence = build_execution_evidence(
        request=request,
        capability=resolved.capability,
        prompt=resolved.prompt,
        provider_execution=resolved.provider_execution,
        safety_outcome=resolved.safety_outcome,
    )
    return TaskExecutionResponse(
        status=TaskExecutionStatus.COMPLETED,
        task_id=resolved.capability.task_id,
        category=resolved.capability.category,
        output_label=resolved.capability.output_label,
        result=TaskExecutionResult(
            message=resolved.provider_execution.message,
            structured_output={
                **resolved.provider_execution.structured_output,
                "input_mode": request.input_mode,
                "caller_app": request.caller.caller_app,
            },
        ),
        evidence=evidence,
        audit=TaskAuditMetadata(
            request_id=resolved.request_id,
            task_id=resolved.capability.task_id,
            output_label=resolved.capability.output_label,
            prompt_version=resolved.prompt.prompt_version,
            provider_mode=resolved.provider_execution.provider_mode,
            safety=resolved.safety_outcome,
            generated_at=resolved.generated_at,
            stubbed=resolved.provider_execution.stubbed,
        ),
    )


def persist_task_execution_audit(
    request: TaskExecutionRequest,
    *,
    response: TaskExecutionResponse,
) -> None:
    get_audit_store().save(
        AuditRecordResponse(
            request_id=response.audit.request_id,
            task_id=response.task_id,
            caller_app=request.caller.caller_app,
            correlation_id=request.caller.correlation_id,
            prompt_version=response.audit.prompt_version,
            provider_mode=response.audit.provider_mode,
            safety_mode=response.audit.safety.safety_mode,
            redaction_posture=response.audit.safety.redaction_posture,
            enforced_safety_controls=response.audit.safety.enforced_controls,
            generated_at=response.audit.generated_at,
            stubbed=response.audit.stubbed,
            context_summary=request.context.summary,
            context_keys=sorted(request.context.payload.keys()),
            source_refs=request.context.source_refs,
            result_preview=response.result.message,
            structured_output=response.result.structured_output,
        )
    )
