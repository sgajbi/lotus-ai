from typing import Any, cast

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.prompts import (
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptManagementMode,
    PromptRolloutRole,
    PromptSelectionTraceDescriptor,
)
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionResponse,
)
from app.contracts.tasks import (
    CallerMetadata,
    CapabilityDescriptor,
    OutputLabel,
    TaskCategory,
    TaskContextEnvelope,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.services.execution_evidence import build_execution_evidence
from app.services.safety_runtime import build_safety_execution_outcome


def _authorization_decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-manage",
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        task_id="explain.v1",
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id="tenant-sg-001",
        summary="Caller is authorized for bounded task execution.",
    )


def test_build_execution_evidence_returns_expected_descriptors() -> None:
    request = TaskExecutionRequest(
        task_id="explain.v1",
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ev-1"),
        context=TaskContextEnvelope(
            summary="Explain rebalance outcome",
            payload={"status": "BLOCKED"},
            source_refs=["lotus-manage:run:reb_001"],
        ),
    )
    capability = CapabilityDescriptor(
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        enabled=True,
        output_label=OutputLabel.EXPLANATION_ONLY,
        description="Explain structured Lotus domain outputs in plain English.",
    )
    prompt = PromptDescriptor(
        task_id="explain.v1",
        prompt_version="foundation.explain.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions="Explain structured outputs conservatively.",
        output_contract_notes="Explanation only.",
    )
    prompt_selection = PromptSelectionTraceDescriptor(
        task_id="explain.v1",
        prompt_version="foundation.explain.v1",
        rollout_role=PromptRolloutRole.ACTIVE,
        selection_reason="Runtime selection resolved through durable prompt rollout state.",
        active_prompt_version="foundation.explain.v1",
        candidate_prompt_version=None,
        previous_active_prompt_version=None,
        latest_control_event=None,
    )
    provider_execution = ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="disabled",
        adapter_kind=ProviderAdapterKind.STUB,
        timeout_ms=4000,
        retry_count=0,
        max_output_tokens=512,
        stubbed=True,
        message="Stub execution completed.",
        structured_output={},
    )
    safety_outcome = build_safety_execution_outcome(OutputLabel.EXPLANATION_ONLY)

    evidence = build_execution_evidence(
        request=request,
        capability=capability,
        authorization=_authorization_decision(),
        prompt=prompt,
        prompt_selection=prompt_selection,
        provider_execution=provider_execution,
        safety_outcome=safety_outcome,
    )

    assert len(evidence.descriptors) == 6
    assert evidence.descriptors[0].evidence_type == "task_contract"
    assert evidence.descriptors[1].evidence_type == "prompt_selection"
    assert evidence.descriptors[1].attributes["rollout_role"] == "ACTIVE"
    assert evidence.descriptors[1].attributes["active_prompt_version"] == "foundation.explain.v1"
    assert evidence.descriptors[1].attributes["latest_control_event"] is None
    assert evidence.descriptors[2].evidence_type == "provider_resolution"
    assert evidence.descriptors[2].attributes["provider_id"] == "text.stub"
    assert evidence.descriptors[2].attributes["provider_mode"] == "disabled"
    assert evidence.descriptors[2].attributes["adapter_kind"] == "STUB"
    assert evidence.descriptors[2].attributes["degradation_status"] == "DOCUMENTED_ONLY"
    assert evidence.descriptors[2].attributes["timeout_ms"] == 4000
    assert evidence.descriptors[2].attributes["retry_count"] == 0
    assert evidence.descriptors[2].attributes["max_output_tokens"] == 512
    assert evidence.descriptors[3].evidence_type == "safety_outcome"
    assert evidence.descriptors[3].attributes["disposition"] == "DOCUMENTED_ONLY"
    assert evidence.descriptors[3].attributes["runtime_redaction_active"] is False
    assert evidence.descriptors[3].attributes["decision_summary"]
    control_results = cast(
        list[dict[str, Any]], evidence.descriptors[3].attributes["control_results"]
    )
    assert control_results[-1]["control_id"] == ("runtime_redaction_engine")
    assert evidence.descriptors[4].evidence_type == "retrieval_posture"
    assert evidence.descriptors[5].evidence_type == "access_control"
    assert evidence.descriptors[5].attributes["outcome"] == "ALLOWED"
    assert evidence.descriptors[5].attributes["tenant_policy_mode"] == "RESTRICTED"


def test_build_execution_evidence_captures_live_retrieval_request_posture() -> None:
    request = TaskExecutionRequest(
        task_id="knowledge_search.v1",
        input_mode=TaskInputMode.STRUCTURED_CONTEXT,
        caller=CallerMetadata(caller_app="lotus-manage", correlation_id="corr-ev-ret-1"),
        context=TaskContextEnvelope(
            summary="Search Lotus knowledge sources",
            payload={"query": "shared ai platform service"},
            source_refs=["lotus-manage:knowledge-search:001"],
        ),
    )
    capability = CapabilityDescriptor(
        task_id="knowledge_search.v1",
        category=TaskCategory.KNOWLEDGE_SEARCH,
        enabled=True,
        output_label=OutputLabel.RETRIEVAL_ANSWER,
        description="Search governed Lotus retrieval sources.",
    )
    prompt = PromptDescriptor(
        task_id="knowledge_search.v1",
        prompt_version="foundation.knowledge_search.v1",
        prompt_kind="system",
        lifecycle_status=PromptLifecycleStatus.ACTIVE,
        management_mode=PromptManagementMode.SEEDED_MEMORY,
        source_reference="app.prompts.registry:_PROMPTS",
        system_instructions="Search Lotus sources conservatively.",
        output_contract_notes="Retrieval answer only.",
    )
    prompt_selection = PromptSelectionTraceDescriptor(
        task_id="knowledge_search.v1",
        prompt_version="foundation.knowledge_search.v1",
        rollout_role=PromptRolloutRole.ACTIVE,
        selection_reason="Runtime selection resolved through durable prompt rollout state.",
        active_prompt_version="foundation.knowledge_search.v1",
        candidate_prompt_version=None,
        previous_active_prompt_version=None,
        latest_control_event=None,
    )
    provider_execution = ProviderExecutionResponse(
        provider_id="retrieval.live_search",
        provider_mode="live_search",
        stubbed=False,
        message="Live retrieval search completed.",
        structured_output={
            "execution_stage": "LIVE_SEARCH",
            "catalog_only": False,
            "retrieval_status": "READY",
            "hit_count": 2,
            "citation_count": 2,
        },
    )
    safety_outcome = build_safety_execution_outcome(OutputLabel.RETRIEVAL_ANSWER)

    evidence = build_execution_evidence(
        request=request,
        capability=capability,
        authorization=_authorization_decision().model_copy(
            update={
                "task_id": "knowledge_search.v1",
                "requested_source_ids": ["lotus-platform-rfcs"],
                "effective_source_ids": ["lotus-platform-rfcs"],
            }
        ),
        prompt=prompt,
        prompt_selection=prompt_selection,
        provider_execution=provider_execution,
        safety_outcome=safety_outcome,
    )

    retrieval_descriptor = evidence.descriptors[4]
    assert retrieval_descriptor.evidence_type == "retrieval_posture"
    assert retrieval_descriptor.attributes["request_execution_stage"] == "LIVE_SEARCH"
    assert retrieval_descriptor.attributes["request_provider_id"] == "retrieval.live_search"
    assert retrieval_descriptor.attributes["request_provider_mode"] == "live_search"
    assert retrieval_descriptor.attributes["catalog_only"] is False
    assert retrieval_descriptor.attributes["hit_count"] == 2
    access_control_descriptor = evidence.descriptors[5]
    assert access_control_descriptor.evidence_type == "access_control"
    assert access_control_descriptor.attributes["effective_source_ids"] == ["lotus-platform-rfcs"]


def test_provider_descriptor_carries_catalogue_binding_attributes() -> None:
    from app.services import execution_evidence as execution_evidence_module

    response = ProviderExecutionResponse(
        provider_id="text.openai",
        provider_mode="openai",
        adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
        model_id="gpt-5.4",
        model_version="gpt-5.4",
        model_catalogue_entry_id="text.openai:gpt-5.4",
        model_revision_pinned=False,
        stubbed=False,
        message="live response",
        structured_output={},
    )

    descriptor = execution_evidence_module._provider_descriptor(provider_execution=response)

    assert descriptor.attributes["model_version"] == "gpt-5.4"
    assert descriptor.attributes["model_catalogue_entry_id"] == "text.openai:gpt-5.4"
    assert descriptor.attributes["model_revision_pinned"] is False


def test_provider_descriptor_omits_catalogue_binding_when_absent() -> None:
    from app.services import execution_evidence as execution_evidence_module

    response = ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="disabled",
        adapter_kind=ProviderAdapterKind.STUB,
        stubbed=True,
        message="Stub execution completed.",
        structured_output={},
    )

    descriptor = execution_evidence_module._provider_descriptor(provider_execution=response)

    assert "model_catalogue_entry_id" not in descriptor.attributes
    assert "model_revision_pinned" not in descriptor.attributes
    assert "model_version" not in descriptor.attributes
