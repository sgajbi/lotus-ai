from __future__ import annotations

from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.prompts import PromptDescriptor
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.retrieval import RetrievalExecutionStatusResponse
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import CapabilityDescriptor, TaskExecutionRequest
from app.services.provider_degradation_state import build_provider_degradation_status
from app.services.retrieval_execution_status import build_retrieval_execution_status


def build_execution_evidence(
    *,
    request: TaskExecutionRequest,
    capability: CapabilityDescriptor,
    prompt: PromptDescriptor,
    provider_execution: ProviderExecutionResponse,
    safety_outcome: SafetyExecutionOutcome,
) -> ExecutionEvidenceBundle:
    retrieval_status = build_retrieval_execution_status()
    return ExecutionEvidenceBundle(
        descriptors=[
            _task_descriptor(capability=capability, request=request),
            _prompt_descriptor(prompt=prompt),
            _provider_descriptor(provider_execution=provider_execution),
            _safety_descriptor(safety_outcome=safety_outcome),
            _retrieval_descriptor(
                retrieval_status=retrieval_status,
                provider_execution=provider_execution,
            ),
        ]
    )


def _task_descriptor(
    *,
    capability: CapabilityDescriptor,
    request: TaskExecutionRequest,
) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="task_contract",
        summary="Execution used the bounded lotus-ai task contract selected by the caller.",
        attributes={
            "task_id": capability.task_id,
            "category": capability.category.value,
            "output_label": capability.output_label.value,
            "input_mode": request.input_mode.value,
            "caller_app": request.caller.caller_app,
        },
    )


def _prompt_descriptor(*, prompt: PromptDescriptor) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="prompt_selection",
        summary="Execution resolved to the currently active prompt definition for the task.",
        attributes={
            "task_id": prompt.task_id,
            "prompt_version": prompt.prompt_version,
            "management_mode": prompt.management_mode.value,
            "source_reference": prompt.source_reference,
        },
    )


def _provider_descriptor(
    *,
    provider_execution: ProviderExecutionResponse,
) -> ExecutionEvidenceDescriptor:
    degradation_status = build_provider_degradation_status()
    return ExecutionEvidenceDescriptor(
        evidence_type="provider_resolution",
        summary="Execution flowed through the provider gateway and resolved to the current provider path.",
        attributes={
            "provider_id": provider_execution.provider_id,
            "provider_mode": provider_execution.provider_mode,
            "stubbed": provider_execution.stubbed,
            "degradation_status": degradation_status.status,
            **(
                {"failure_category": provider_execution.failure_category.value}
                if provider_execution.failure_category is not None
                else {}
            ),
            **(
                {"timeout_ms": provider_execution.timeout_ms}
                if provider_execution.timeout_ms is not None
                else {}
            ),
            **(
                {"retry_count": provider_execution.retry_count}
                if provider_execution.retry_count is not None
                else {}
            ),
            **(
                {"max_output_tokens": provider_execution.max_output_tokens}
                if provider_execution.max_output_tokens is not None
                else {}
            ),
            **(
                {"model_id": provider_execution.model_id}
                if provider_execution.model_id is not None
                else {}
            ),
            **(
                {"provider_request_id": provider_execution.provider_request_id}
                if provider_execution.provider_request_id is not None
                else {}
            ),
            **(
                {"input_tokens": provider_execution.input_tokens}
                if provider_execution.input_tokens is not None
                else {}
            ),
            **(
                {"output_tokens": provider_execution.output_tokens}
                if provider_execution.output_tokens is not None
                else {}
            ),
            **(
                {"total_tokens": provider_execution.total_tokens}
                if provider_execution.total_tokens is not None
                else {}
            ),
            **(
                {"estimated_cost_usd": provider_execution.estimated_cost_usd}
                if provider_execution.estimated_cost_usd is not None
                else {}
            ),
            **(
                {"adapter_kind": provider_execution.adapter_kind.value}
                if provider_execution.adapter_kind is not None
                else {}
            ),
        },
    )


def _safety_descriptor(
    *,
    safety_outcome: SafetyExecutionOutcome,
) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="safety_outcome",
        summary="Execution captured the applied safety posture and enforced control set.",
        attributes={
            "safety_mode": safety_outcome.safety_mode,
            "output_label": safety_outcome.output_label,
            "redaction_posture": safety_outcome.redaction_posture.value,
            "disposition": safety_outcome.disposition.value,
            "runtime_redaction_active": safety_outcome.runtime_redaction_active,
            "enforced_controls": safety_outcome.enforced_controls,
            "control_results": [
                {
                    "control_id": result.control_id,
                    "execution_state": result.execution_state.value,
                    "summary": result.summary,
                }
                for result in safety_outcome.control_results
            ],
            "decision_summary": safety_outcome.decision_summary,
        },
    )


def _retrieval_descriptor(
    *,
    retrieval_status: RetrievalExecutionStatusResponse,
    provider_execution: ProviderExecutionResponse,
) -> ExecutionEvidenceDescriptor:
    retrieval_attributes: dict[str, object] = {
        "retrieval_mode": retrieval_status.retrieval_mode,
        "execution_stage": retrieval_status.execution_stage.value,
        "live_search_enabled": retrieval_status.live_search_enabled,
        "live_indexing_enabled": retrieval_status.live_indexing_enabled,
    }
    if provider_execution.provider_id.startswith("retrieval."):
        structured_output = provider_execution.structured_output
        retrieval_attributes.update(
            {
                "request_execution_stage": structured_output.get("execution_stage"),
                "request_provider_id": provider_execution.provider_id,
                "request_provider_mode": provider_execution.provider_mode,
                "catalog_only": structured_output.get("catalog_only"),
                "retrieval_status": structured_output.get("retrieval_status"),
                "hit_count": structured_output.get("hit_count"),
                "citation_count": structured_output.get("citation_count"),
            }
        )
    return ExecutionEvidenceDescriptor(
        evidence_type="retrieval_posture",
        summary="Execution captured the current retrieval execution posture for cross-cutting evidence.",
        attributes=retrieval_attributes,
    )
