from __future__ import annotations

from app.contracts.access_control import AuthorizationDecision
from app.contracts.capability_requirements import (
    REQUIREMENTS_ENFORCED,
    REQUIREMENTS_NOT_ENFORCED,
    REQUIREMENTS_PARTIALLY_ENFORCED,
)
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.output_validation import OutputValidationOutcome
from app.contracts.prompts import PromptDescriptor, PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderExecutionResponse, RoutingDecisionDescriptor
from app.contracts.retrieval import RetrievalExecutionStatusResponse
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import CapabilityDescriptor, TaskExecutionRequest
from app.services.provider_degradation_state import build_provider_degradation_status
from app.services.retrieval_execution_status import build_retrieval_execution_status


def build_execution_evidence(
    *,
    request: TaskExecutionRequest,
    capability: CapabilityDescriptor,
    authorization: AuthorizationDecision,
    prompt: PromptDescriptor,
    prompt_selection: PromptSelectionTraceDescriptor,
    provider_execution: ProviderExecutionResponse,
    safety_outcome: SafetyExecutionOutcome,
    output_validation: OutputValidationOutcome,
) -> ExecutionEvidenceBundle:
    retrieval_status = build_retrieval_execution_status()
    descriptors = [
        _task_descriptor(capability=capability, request=request),
        _prompt_descriptor(prompt=prompt, prompt_selection=prompt_selection),
        _provider_descriptor(provider_execution=provider_execution),
    ]
    routing_decision = getattr(provider_execution, "routing_decision", None)
    if routing_decision is not None:
        descriptors.append(build_routing_decision_descriptor(routing_decision=routing_decision))
    descriptors.extend(
        [
            _safety_descriptor(safety_outcome=safety_outcome),
            _retrieval_descriptor(
                retrieval_status=retrieval_status,
                provider_execution=provider_execution,
            ),
            _access_control_descriptor(authorization=authorization),
            _output_validation_descriptor(output_validation=output_validation),
        ]
    )
    if request.requirements is not None:
        descriptors.append(
            _capability_requirements_descriptor(
                request=request, provider_execution=provider_execution
            )
        )
    return ExecutionEvidenceBundle(descriptors=descriptors)


def _capability_requirements_descriptor(
    *, request: TaskExecutionRequest, provider_execution: ProviderExecutionResponse
) -> ExecutionEvidenceDescriptor:
    """Declared workload requirements, with their enforcement posture stated.

    Recording a requirement without saying whether anything enforces it would
    let a consumer believe a ceiling is being held when nothing holds it -
    the declared-versus-measured defect this platform keeps finding. The
    posture derives from the routing decision that actually ran (issue #244,
    S3): a decision that enforced every declared dimension reports ENFORCED, a
    partial one names both halves, and an execution with no routing decision
    (the stub path) honestly reports NOT_ENFORCED rather than borrowing a
    guarantee no filter provided.
    """

    assert request.requirements is not None
    declared = request.requirements.declared_dimensions()
    decision = getattr(provider_execution, "routing_decision", None)
    enforced = list(decision.requirements_enforced_dimensions) if decision is not None else []
    unenforced = (
        list(decision.requirements_unenforced_dimensions)
        if decision is not None and enforced
        else sorted(declared)
    )
    if not enforced:
        posture = REQUIREMENTS_NOT_ENFORCED
    elif unenforced:
        posture = REQUIREMENTS_PARTIALLY_ENFORCED
    else:
        posture = REQUIREMENTS_ENFORCED
    return ExecutionEvidenceDescriptor(
        evidence_type="capability_requirements",
        summary=(
            f"The caller declared workload capability requirements; enforcement is {posture} "
            "for this execution, with the enforced and unenforced dimensions listed."
        ),
        attributes={
            "declared": declared,
            "requirements_enforcement": posture,
            "enforced_dimensions": enforced,
            "unenforced_dimensions": unenforced,
        },
    )


def _output_validation_descriptor(
    *, output_validation: OutputValidationOutcome
) -> ExecutionEvidenceDescriptor:
    """The output's verdict, carried as evidence rather than as a new field.

    Downstream surfaces already persist and render this bundle, so the verdict
    reaches the run record, the consumer view, the operator profile and the
    accepted-output projector without a migration or a per-projection field
    (issue #231).

    ``findings`` is deliberately excluded: those statements quote the tokens
    and references that failed a rule, so they carry output content, and this
    bundle is persisted and read under a different redaction posture than the
    response that produced it. Rule identifiers say which rule failed without
    reproducing what it saw.
    """

    return ExecutionEvidenceDescriptor(
        evidence_type="output_validation",
        summary=(
            f"Deterministic output validation returned {output_validation.validation_state.value} "
            f"under ruleset {output_validation.ruleset_version}; this output is "
            f"{output_validation.authority}."
        ),
        attributes={
            "validation_state": output_validation.validation_state.value,
            "authority": output_validation.authority,
            "ruleset_version": output_validation.ruleset_version,
            "failed_rule_ids": list(output_validation.failed_rule_ids),
        },
    )


def build_routing_decision_descriptor(
    *,
    routing_decision: RoutingDecisionDescriptor,
) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="routing_decision",
        summary="Execution recorded the routing-policy decision that selected its provider path.",
        attributes=routing_decision.model_dump(mode="json"),
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


def _prompt_descriptor(
    *,
    prompt: PromptDescriptor,
    prompt_selection: PromptSelectionTraceDescriptor,
) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="prompt_selection",
        summary="Execution resolved to the currently active prompt definition for the task.",
        attributes={
            "task_id": prompt.task_id,
            "prompt_version": prompt.prompt_version,
            "management_mode": prompt.management_mode.value,
            "source_reference": prompt.source_reference,
            "rollout_role": prompt_selection.rollout_role.value,
            "active_prompt_version": prompt_selection.active_prompt_version,
            "candidate_prompt_version": prompt_selection.candidate_prompt_version,
            "previous_active_prompt_version": prompt_selection.previous_active_prompt_version,
            "latest_control_event": (
                prompt_selection.latest_control_event.model_dump(mode="json")
                if prompt_selection.latest_control_event is not None
                else None
            ),
        },
    )


def _provider_descriptor(
    *,
    provider_execution: ProviderExecutionResponse,
) -> ExecutionEvidenceDescriptor:
    # Evidence is built after the gateway's per-candidate config override
    # has exited, so an ambient read would report the primary's breaker for
    # an alternate-served execution. Ask about the identity that served
    # (issue #237).
    degradation_status = build_provider_degradation_status(provider_execution.provider_id)
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
            # The catalogue-binding attributes are read defensively: responses
            # predating the binding (and stub paths) simply omit them.
            **(
                {"model_version": model_version}
                if (model_version := getattr(provider_execution, "model_version", None)) is not None
                else {}
            ),
            **(
                {"model_catalogue_entry_id": catalogue_entry_id}
                if (
                    catalogue_entry_id := getattr(
                        provider_execution, "model_catalogue_entry_id", None
                    )
                )
                is not None
                else {}
            ),
            **(
                {"model_revision_pinned": revision_pinned}
                if (revision_pinned := getattr(provider_execution, "model_revision_pinned", None))
                is not None
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


def _access_control_descriptor(
    *,
    authorization: AuthorizationDecision,
) -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type="access_control",
        summary="Execution captured the caller authorization decision applied to the request path.",
        attributes={
            "caller_app": authorization.caller_app,
            "capability_type": authorization.capability_type.value,
            "outcome": authorization.outcome.value,
            "allowed": authorization.allowed,
            "tenant_policy_mode": authorization.tenant_policy_mode.value,
            "tenant_id": authorization.tenant_id,
            "task_id": authorization.task_id,
            "requested_source_ids": authorization.requested_source_ids,
            "effective_source_ids": authorization.effective_source_ids,
            "summary": authorization.summary,
        },
    )
