from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.audit import AuditRecordResponse
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.prompts import PromptRolloutRole, PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderAdapterKind
from app.contracts.safety import RedactionPosture
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.repositories.memory_audit_repository import InMemoryAuditRepository
from app.services.safety_runtime import build_safety_execution_outcome_from_record


def _authorization() -> AuthorizationDecision:
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


def test_in_memory_audit_store_save_and_get() -> None:
    store = InMemoryAuditRepository()
    record = AuditRecordResponse(
        request_id="air_test",
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-123",
        requested_by="ops.user@lotus",
        tenant_id="tenant-sg-001",
        prompt_version="foundation.explain.v1",
        prompt_selection=PromptSelectionTraceDescriptor(
            task_id="explain.v1",
            prompt_version="foundation.explain.v1",
            rollout_role=PromptRolloutRole.ACTIVE,
            selection_reason="Runtime selection resolved through durable prompt rollout state.",
            active_prompt_version="foundation.explain.v1",
            candidate_prompt_version=None,
            previous_active_prompt_version=None,
            latest_control_event=None,
        ),
        provider_mode="disabled",
        provider_id="text.stub",
        adapter_kind=ProviderAdapterKind.STUB,
        model_id=None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.EXPLANATION_ONLY,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling", "correlation_and_audit"],
        ),
        authorization=_authorization(),
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Explain rebalance outcome",
        context_keys=["status"],
        source_refs=["lotus-manage:run:reb_1"],
        result_preview="Stub execution completed.",
        structured_output={"phase": "foundation"},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )

    store.save(record)

    assert store.get("air_test") == record
    assert store.get("air_missing") is None


def test_in_memory_audit_store_list_filters_and_orders_latest_first() -> None:
    store = InMemoryAuditRepository()
    first = AuditRecordResponse(
        request_id="air_old",
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id="corr-old",
        requested_by="ops.user@lotus",
        tenant_id="tenant-sg-001",
        prompt_version="foundation.explain.v1",
        prompt_selection=PromptSelectionTraceDescriptor(
            task_id="explain.v1",
            prompt_version="foundation.explain.v1",
            rollout_role=PromptRolloutRole.ACTIVE,
            selection_reason="Runtime selection resolved through durable prompt rollout state.",
            active_prompt_version="foundation.explain.v1",
            candidate_prompt_version=None,
            previous_active_prompt_version=None,
            latest_control_event=None,
        ),
        provider_mode="disabled",
        provider_id="text.stub",
        adapter_kind=ProviderAdapterKind.STUB,
        model_id=None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.EXPLANATION_ONLY,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling", "correlation_and_audit"],
        ),
        authorization=_authorization(),
        generated_at="2026-03-22T00:00:00Z",
        stubbed=True,
        context_summary="Old record",
        context_keys=["status"],
        source_refs=[],
        result_preview="Old",
        structured_output={},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="Task contract selected.",
                    attributes={"task_id": "explain.v1"},
                )
            ]
        ),
    )
    second = first.model_copy(
        update={
            "request_id": "air_new",
            "task_id": "summarize.v1",
            "category": TaskCategory.SUMMARIZE,
            "output_label": OutputLabel.DRAFT,
            "caller_app": "lotus-advise",
            "requested_by": "advisor.user@lotus",
            "tenant_id": "tenant-us-002",
            "generated_at": "2026-03-22T01:00:00Z",
        }
    )
    store.save(first)
    store.save(second)

    all_records = store.list()
    advise_records = store.list(caller_app="lotus-advise")
    summarize_records = store.list(category="summarize")
    draft_records = store.list(output_label="DRAFT")
    tenant_records = store.list(tenant_id="tenant-us-002")
    requester_records = store.list(requested_by="advisor.user@lotus")

    assert [record.request_id for record in all_records] == ["air_new", "air_old"]
    assert [record.request_id for record in advise_records] == ["air_new"]
    assert [record.request_id for record in summarize_records] == ["air_new"]
    assert [record.request_id for record in draft_records] == ["air_new"]
    assert [record.request_id for record in tenant_records] == ["air_new"]
    assert [record.request_id for record in requester_records] == ["air_new"]
