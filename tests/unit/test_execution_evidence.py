from app.contracts.prompts import PromptDescriptor, PromptLifecycleStatus, PromptManagementMode
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
        prompt=prompt,
        provider_execution=provider_execution,
        safety_outcome=safety_outcome,
    )

    assert len(evidence.descriptors) == 5
    assert evidence.descriptors[0].evidence_type == "task_contract"
    assert evidence.descriptors[1].evidence_type == "prompt_selection"
    assert evidence.descriptors[2].evidence_type == "provider_resolution"
    assert evidence.descriptors[2].attributes["adapter_kind"] == "STUB"
    assert evidence.descriptors[2].attributes["degradation_status"] == "DOCUMENTED_ONLY"
    assert evidence.descriptors[2].attributes["timeout_ms"] == 4000
    assert evidence.descriptors[2].attributes["retry_count"] == 0
    assert evidence.descriptors[2].attributes["max_output_tokens"] == 512
    assert evidence.descriptors[3].evidence_type == "safety_outcome"
    assert evidence.descriptors[4].evidence_type == "retrieval_posture"


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
        prompt=prompt,
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
