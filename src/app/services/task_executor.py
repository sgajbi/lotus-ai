from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.audit import AuditRecordResponse
from app.contracts.providers import ProviderExecutionRequest
from app.contracts.tasks import (
    TaskExecutionRequest,
    TaskExecutionResponse,
    TaskExecutionResult,
    TaskExecutionStatus,
    TaskAuditMetadata,
)
from app.services.audit_store import get_audit_store
from app.services.capability_catalog import get_capability_by_task_id
from app.services.provider_gateway import execute_text_generation
from app.services.prompt_registry import get_prompt_or_raise


def execute_task(request: TaskExecutionRequest) -> TaskExecutionResponse:
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
    prompt = get_prompt_or_raise(request.task_id)
    request_id = f"air_{uuid4().hex}"
    provider_execution = execute_text_generation(
        ProviderExecutionRequest(
            task_id=capability.task_id,
            caller_app=request.caller.caller_app,
            prompt_version=prompt.prompt_version,
            context_summary=request.context.summary,
            context_payload=request.context.payload,
            source_refs=request.context.source_refs,
        )
    )
    response = TaskExecutionResponse(
        status=TaskExecutionStatus.COMPLETED,
        task_id=capability.task_id,
        category=capability.category,
        output_label=capability.output_label,
        result=TaskExecutionResult(
            message=provider_execution.message,
            structured_output={
                **provider_execution.structured_output,
                "input_mode": request.input_mode,
                "caller_app": request.caller.caller_app,
            },
        ),
        audit=TaskAuditMetadata(
            request_id=request_id,
            task_id=capability.task_id,
            output_label=capability.output_label,
            prompt_version=prompt.prompt_version,
            provider_mode=provider_execution.provider_mode,
            generated_at=datetime.now(UTC).isoformat(),
            stubbed=provider_execution.stubbed,
        ),
    )
    get_audit_store().save(
        AuditRecordResponse(
            request_id=response.audit.request_id,
            task_id=response.task_id,
            caller_app=request.caller.caller_app,
            correlation_id=request.caller.correlation_id,
            prompt_version=response.audit.prompt_version,
            provider_mode=response.audit.provider_mode,
            generated_at=response.audit.generated_at,
            stubbed=response.audit.stubbed,
            context_summary=request.context.summary,
            context_keys=sorted(request.context.payload.keys()),
            source_refs=request.context.source_refs,
            result_preview=response.result.message,
            structured_output=response.result.structured_output,
        )
    )
    return response
