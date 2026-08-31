from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException

from app.config import settings
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.providers import ProviderFailureCategory
from app.contracts.tasks import (
    TaskAuditMetadata,
    TaskExecutionRequest,
    TaskExecutionResponse,
    TaskExecutionResult,
    TaskExecutionStatus,
)
from app.services.audit_store import get_audit_store
from app.services.execution_evidence import build_routing_decision_descriptor
from app.services.knowledge_answer_execution import execute_knowledge_answer
from app.services.output_validation import validate_provider_output
from app.services.knowledge_search_execution import execute_knowledge_search
from app.services.provider_request_builder import build_provider_execution_request
from app.services.caller_policy_store import get_caller_policy_repository
from app.services.safety_enforcement import (
    apply_safety_enforcement,
    merge_redaction_findings,
    redact_content_for_audit,
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
    provider_request = None
    if context.capability.category == TaskCategory.KNOWLEDGE_SEARCH:
        provider_execution = execute_knowledge_search(context=context)
    elif context.capability.category == TaskCategory.KNOWLEDGE_ANSWER:
        provider_execution = execute_knowledge_answer(context=context)
    else:
        provider_request = build_provider_execution_request(context=context)
        provider_execution = execute_text_generation(provider_request)
    # Deterministic output validation runs on the provider's actual output,
    # BEFORE safety redaction: redaction must never be able to erase a
    # fabricated reference and flip a verdict (issue #156).
    output_validation = validate_provider_output(
        structured_output=provider_execution.structured_output,
        supplied_source_refs=context.request.context.source_refs,
        salvaged_json=bool(provider_execution.structured_output.get("strict_json_salvaged", False)),
        runtime_profile=settings.runtime_profile,
    )
    client_identifiers = _caller_redaction_identifiers(context.request.caller.caller_app)
    safe_provider_execution, safety_outcome = apply_safety_enforcement(
        policy=resolve_safety_policy_for_output(context.capability.output_label),
        provider_execution=provider_execution,
        client_identifiers=client_identifiers,
        redaction_allowlisted_types=context.capability.redaction_allowlisted_types,
    )
    _, summary_redactions = redact_content_for_audit(
        context.request.context.summary,
        client_identifiers=client_identifiers,
        allowlisted_types=context.capability.redaction_allowlisted_types,
    )
    if summary_redactions:
        safety_outcome = safety_outcome.model_copy(
            update={
                "redactions": merge_redaction_findings(
                    safety_outcome.redactions, summary_redactions
                )
            }
        )
    return ResolvedTaskExecution(
        context=context,
        provider_request=provider_request,
        provider_execution=safe_provider_execution,
        safety_outcome=safety_outcome,
        output_validation=output_validation,
    )


def _caller_redaction_identifiers(caller_app: str) -> list[str]:
    policy = get_caller_policy_repository().get_policy(caller_app)
    if policy is None:
        return []
    return list(policy.redaction_client_identifiers)


def build_task_execution_response(
    *,
    resolved: ResolvedTaskExecution,
) -> TaskExecutionResponse:
    return map_task_execution_response(resolved=resolved)


def build_failed_task_execution_response(
    *,
    context: TaskExecutionContext,
    exc: HTTPException,
) -> TaskExecutionResponse:
    detail = _http_exception_detail(exc)
    routing_decision = getattr(exc, "routing_decision", None)
    failure_descriptors = [
        ExecutionEvidenceDescriptor(
            evidence_type="task_contract",
            summary="Workflow-pack execution retained the bounded task contract despite runtime failure.",
            attributes={
                "task_id": context.capability.task_id,
                "output_label": context.capability.output_label.value,
            },
        ),
        ExecutionEvidenceDescriptor(
            evidence_type="workflow_pack_execution_failure",
            summary="The explicit workflow-pack execution seam recorded the runtime failure into the durable run ledger.",
            attributes={
                "status_code": exc.status_code,
                "detail": detail,
                "failure_category": _infer_failure_category(detail),
            },
        ),
    ]
    if routing_decision is not None:
        failure_descriptors.append(
            build_routing_decision_descriptor(routing_decision=routing_decision)
        )
    failure_descriptors.append(
        ExecutionEvidenceDescriptor(
            evidence_type="access_control",
            summary="The caller authorization posture was resolved before the runtime failure occurred.",
            attributes={
                "outcome": context.authorization.outcome.value,
                "caller_app": context.request.caller.caller_app,
            },
        )
    )
    return TaskExecutionResponse(
        status=TaskExecutionStatus.FAILED,
        task_id=context.capability.task_id,
        category=context.capability.category,
        output_label=context.capability.output_label,
        result=TaskExecutionResult(
            message=detail,
            structured_output={
                "failure_detail": detail,
                "failure_status_code": exc.status_code,
                "failure_category": _infer_failure_category(detail),
                "input_mode": context.request.input_mode,
                "caller_app": context.request.caller.caller_app,
            },
        ),
        audit=TaskAuditMetadata(
            request_id=context.request_id,
            task_id=context.capability.task_id,
            output_label=context.capability.output_label,
            prompt_version=context.prompt.prompt_version,
            prompt_selection=context.prompt_selection,
            provider_mode=settings.provider_mode,
            provider_id=settings.live_text_provider_id or "provider.unavailable",
            adapter_kind=None,
            model_id=settings.live_text_model_id,
            model_version=settings.live_text_model_version,
            safety=context.safety_outcome,
            authorization=context.authorization,
            generated_at=_utcnow(),
            stubbed=False,
            routing_decision=routing_decision,
            prompt_content_sha256=context.prompt.content_sha256,
        ),
        evidence=ExecutionEvidenceBundle(descriptors=failure_descriptors),
    )


def persist_task_execution_audit(
    *,
    context: TaskExecutionContext,
    response: TaskExecutionResponse,
) -> None:
    get_audit_store().save(map_audit_record(context=context, response=response))


def _http_exception_detail(exc: HTTPException) -> str:
    if isinstance(exc.detail, str) and exc.detail.strip():
        return exc.detail.strip()
    return "Workflow-pack execution failed before lotus-ai could produce a completed task result."


def _infer_failure_category(detail: str) -> str | None:
    prefix, _, _ = detail.partition(":")
    try:
        return ProviderFailureCategory(prefix).value
    except ValueError:
        return None


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
