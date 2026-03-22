from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.tasks import (
    CapabilityDescriptor,
    TaskExecutionRequest,
    TaskExecutionResponse,
    TaskExecutionResult,
    TaskExecutionStatus,
    TaskAuditMetadata,
)
from app.services.capability_catalog import get_capability_by_task_id

PROMPT_VERSION = "foundation.stub.v1"


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

    return TaskExecutionResponse(
        status=TaskExecutionStatus.COMPLETED,
        task_id=capability.task_id,
        category=capability.category,
        output_label=capability.output_label,
        result=_build_stub_result(request=request, capability=capability),
        audit=TaskAuditMetadata(
            request_id=f"air_{uuid4().hex}",
            task_id=capability.task_id,
            output_label=capability.output_label,
            prompt_version=PROMPT_VERSION,
            provider_mode=settings.provider_mode,
            generated_at=datetime.now(UTC).isoformat(),
            stubbed=True,
        ),
    )


def _build_stub_result(
    *,
    request: TaskExecutionRequest,
    capability: CapabilityDescriptor,
) -> TaskExecutionResult:
    return TaskExecutionResult(
        message=(
            "Stub execution completed for foundation-phase task "
            f"{capability.task_id} requested by {request.caller.caller_app}."
        ),
        structured_output={
            "phase": settings.delivery_phase,
            "input_mode": request.input_mode,
            "caller_app": request.caller.caller_app,
            "context_summary": request.context.summary,
            "context_keys": sorted(request.context.payload.keys()),
            "source_refs": request.context.source_refs,
            "stub_reason": (
                "lotus-ai foundation phase exposes governed integration contracts "
                "before live provider execution is enabled."
            ),
        },
    )
