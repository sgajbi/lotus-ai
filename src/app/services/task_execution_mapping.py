from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.contracts.audit import AuditRecordResponse
from app.contracts.safety import RedactionPosture
from app.contracts.tasks import (
    TaskAuditMetadata,
    TaskExecutionResponse,
    TaskExecutionResult,
    TaskExecutionStatus,
)
from app.services.execution_evidence import build_execution_evidence
from app.services.task_execution_models import ResolvedTaskExecution, TaskExecutionContext
from app.services.provider_execution_config import compute_provider_config_sha256

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
        authorization=context.authorization,
        prompt=context.prompt,
        prompt_selection=context.prompt_selection,
        provider_execution=resolved.provider_execution,
        safety_outcome=resolved.safety_outcome,
    )
    execution_status = (
        TaskExecutionStatus.REJECTED
        if resolved.safety_outcome.disposition.value == "BLOCKED"
        else TaskExecutionStatus.COMPLETED
    )
    return TaskExecutionResponse(
        status=execution_status,
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
            prompt_selection=context.prompt_selection,
            provider_mode=resolved.provider_execution.provider_mode,
            provider_id=resolved.provider_execution.provider_id,
            adapter_kind=resolved.provider_execution.adapter_kind,
            model_id=resolved.provider_execution.model_id,
            model_version=resolved.provider_execution.model_version,
            model_catalogue_entry_id=resolved.provider_execution.model_catalogue_entry_id,
            model_revision_pinned=resolved.provider_execution.model_revision_pinned,
            routing_decision=resolved.provider_execution.routing_decision,
            prompt_content_sha256=context.prompt.content_sha256,
            sampling_parameters=_sampling_parameters(resolved),
            provider_config_sha256=_provider_config_sha256(resolved),
            safety=resolved.safety_outcome,
            authorization=context.authorization,
            generated_at=_utcnow(),
            stubbed=resolved.provider_execution.stubbed,
        ),
    )


def build_task_result_payload(
    *,
    context: TaskExecutionContext,
    resolved: ResolvedTaskExecution,
) -> dict[str, object]:
    if _is_domain_only_workflow_pack_output(resolved.provider_execution.structured_output):
        return dict(resolved.provider_execution.structured_output)
    payload = {
        **resolved.provider_execution.structured_output,
        "input_mode": context.request.input_mode,
    }
    # Caller identity is echoed only when deterministic key minimization did
    # NOT run for this output. Keyed to the control that actually executed,
    # not to runtime_redaction_active - that flag now truthfully reports the
    # (absent) content-redaction engine (issue #150), not minimization.
    if not (
        "structured_output_key_minimization" in resolved.safety_outcome.enforced_controls
        and resolved.safety_outcome.redaction_posture == RedactionPosture.MINIMIZATION_REQUIRED
    ):
        payload["caller_app"] = context.request.caller.caller_app
    return payload


def _is_domain_only_workflow_pack_output(payload: dict[str, object]) -> bool:
    workflow_pack_family = payload.get("workflow_pack_family")
    return isinstance(workflow_pack_family, str) and workflow_pack_family.startswith(
        "advisory_copilot_"
    )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sampling_parameters(resolved: ResolvedTaskExecution) -> dict[str, object] | None:
    request = resolved.provider_request
    if request is None:
        return None
    return {
        "temperature": request.temperature,
        "top_p": request.top_p,
        "seed": request.seed,
        "max_output_tokens": request.max_output_tokens,
    }


def _provider_config_sha256(resolved: ResolvedTaskExecution) -> str | None:
    request = resolved.provider_request
    if request is None:
        return None
    execution = resolved.provider_execution
    return compute_provider_config_sha256(
        provider_mode=execution.provider_mode,
        provider_id=execution.provider_id,
        model_id=execution.model_id,
        model_version=execution.model_version,
        temperature=request.temperature,
        top_p=request.top_p,
        seed=request.seed,
        max_output_tokens=request.max_output_tokens,
    )


def map_audit_record(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
) -> AuditRecordResponse:
    return AuditRecordResponse(
        request_id=response.audit.request_id,
        execution_status=response.status,
        task_id=response.task_id,
        category=response.category,
        output_label=response.output_label,
        caller_app=context.request.caller.caller_app,
        correlation_id=context.request.caller.correlation_id,
        requested_by=context.request.caller.requested_by,
        tenant_id=context.request.caller.tenant_id,
        prompt_version=response.audit.prompt_version,
        prompt_selection=response.audit.prompt_selection,
        provider_mode=response.audit.provider_mode,
        provider_id=response.audit.provider_id,
        adapter_kind=response.audit.adapter_kind,
        model_id=response.audit.model_id,
        model_version=response.audit.model_version,
        model_catalogue_entry_id=response.audit.model_catalogue_entry_id,
        model_revision_pinned=response.audit.model_revision_pinned,
        routing_decision=response.audit.routing_decision,
        prompt_content_sha256=response.audit.prompt_content_sha256,
        sampling_parameters=response.audit.sampling_parameters,
        provider_config_sha256=response.audit.provider_config_sha256,
        safety_mode=response.audit.safety.safety_mode,
        redaction_posture=response.audit.safety.redaction_posture,
        enforced_safety_controls=response.audit.safety.enforced_controls,
        safety_outcome=response.audit.safety,
        authorization=response.audit.authorization,
        generated_at=response.audit.generated_at,
        stubbed=response.audit.stubbed,
        context_summary=context.request.context.summary,
        context_keys=sorted(context.request.context.payload.keys()),
        source_refs=context.request.context.source_refs,
        result_preview=response.result.message,
        structured_output=response.result.structured_output,
        evidence=response.evidence,
    )
