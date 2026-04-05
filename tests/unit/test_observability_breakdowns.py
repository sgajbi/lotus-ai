from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.async_runtime import (
    AsyncJobArtifactDescriptor,
    AsyncJobRecordSource,
    AsyncJobStatus,
)
from app.contracts.audit import AuditRecordResponse
from app.contracts.evidence import ExecutionEvidenceBundle, ExecutionEvidenceDescriptor
from app.contracts.observability import ObservabilityCapabilityKind
from app.contracts.prompts import PromptRolloutRole, PromptSelectionTraceDescriptor
from app.contracts.safety import RedactionPosture
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.services.observability_breakdowns import (
    _build_capability_samples,
    _build_caller_samples,
    _build_tenant_samples,
)
from app.services.safety_runtime import build_safety_execution_outcome_from_record


def _authorization(
    *, caller_app: str, task_id: str, tenant_id: str | None, allowed: bool
) -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app=caller_app,
        capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
        outcome=AuthorizationOutcome.ALLOWED
        if allowed
        else AuthorizationOutcome.BLOCKED_TENANT_NOT_ALLOWED,
        allowed=allowed,
        tenant_policy_mode=TenantPolicyMode.RESTRICTED,
        task_id=task_id,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=tenant_id,
        summary="Synthetic authorization outcome for observability breakdown tests.",
    )


def _record(
    *,
    request_id: str,
    caller_app: str,
    task_id: str,
    tenant_id: str | None,
    provider_mode: str,
    allowed: bool,
    source_ids: list[str] | None = None,
) -> AuditRecordResponse:
    return AuditRecordResponse(
        request_id=request_id,
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id=task_id,
        category=TaskCategory.KNOWLEDGE_ANSWER
        if task_id.startswith("knowledge_")
        else TaskCategory.EXPLAIN,
        output_label=OutputLabel.RETRIEVAL_ANSWER
        if task_id.startswith("knowledge_")
        else OutputLabel.EXPLANATION_ONLY,
        caller_app=caller_app,
        correlation_id=f"corr-{request_id}",
        requested_by=None,
        tenant_id=tenant_id,
        prompt_version="foundation.v1",
        prompt_selection=PromptSelectionTraceDescriptor(
            task_id=task_id,
            prompt_version="foundation.v1",
            rollout_role=PromptRolloutRole.ACTIVE,
            selection_reason="test",
            active_prompt_version="foundation.v1",
            candidate_prompt_version=None,
            previous_active_prompt_version=None,
            latest_control_event=None,
        ),
        provider_mode=provider_mode,
        provider_id=(
            "text.stub"
            if provider_mode in {"disabled", "stub"}
            else "retrieval.catalog"
            if provider_mode == "catalog_only"
            else "retrieval.answer"
            if provider_mode == "catalog_answer"
            else "text.openai"
        ),
        adapter_kind=(
            "STUB"
            if provider_mode in {"disabled", "stub"}
            else "OPENAI_LIVE"
            if provider_mode == "openai"
            else None
        ),
        model_id="gpt-5.4" if provider_mode == "openai" else None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling", "correlation_and_audit"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.RETRIEVAL_ANSWER
            if task_id.startswith("knowledge_")
            else OutputLabel.EXPLANATION_ONLY,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling", "correlation_and_audit"],
        ),
        authorization=_authorization(
            caller_app=caller_app, task_id=task_id, tenant_id=tenant_id, allowed=allowed
        ),
        generated_at="2026-03-24T00:00:00Z",
        stubbed=provider_mode in {"disabled", "catalog_only"},
        context_summary="synthetic",
        context_keys=["payload"],
        source_refs=[],
        result_preview="ok",
        structured_output={"source_ids": source_ids or []},
        evidence=ExecutionEvidenceBundle(
            descriptors=[
                ExecutionEvidenceDescriptor(
                    evidence_type="task_contract",
                    summary="test",
                    attributes={"task_id": task_id},
                )
            ]
        ),
    )


def _job(*, job_id: str, caller_app: str, job_type: str) -> AsyncJobArtifactDescriptor:
    return AsyncJobArtifactDescriptor(
        job_id=job_id,
        job_type=job_type,
        target_id=None,
        status=AsyncJobStatus.QUEUED,
        record_source=AsyncJobRecordSource.RUNTIME_STATE,
        submitted_at="2026-03-24T00:00:00Z",
        caller_app=caller_app,
        related_evaluation_run_id=None,
        execution_path="queue_backed_workers",
        notes="test",
    )


def test_build_caller_samples_counts_task_and_async_activity() -> None:
    records = [
        _record(
            request_id="air-1",
            caller_app="lotus-manage",
            task_id="knowledge_answer.v1",
            tenant_id="tenant-sg-001",
            provider_mode="catalog_only",
            allowed=True,
            source_ids=["lotus-platform-rfcs"],
        ),
        _record(
            request_id="air-2",
            caller_app="lotus-manage",
            task_id="explain.v1",
            tenant_id="tenant-sg-001",
            provider_mode="openai",
            allowed=True,
        ),
    ]
    jobs = [_job(job_id="job-1", caller_app="lotus-manage", job_type="evaluation_execution")]

    samples = _build_caller_samples(records=records, jobs=jobs)
    sample = samples[0]

    assert sample.caller_app == "lotus-manage"
    assert sample.execution_count == 2
    assert sample.retrieval_execution_count == 1
    assert sample.live_provider_execution_count == 1
    assert sample.async_job_count == 1


def test_build_tenant_samples_excludes_unauthorized_records() -> None:
    records = [
        _record(
            request_id="air-1",
            caller_app="lotus-manage",
            task_id="explain.v1",
            tenant_id="tenant-sg-001",
            provider_mode="disabled",
            allowed=True,
        ),
        _record(
            request_id="air-2",
            caller_app="lotus-manage",
            task_id="explain.v1",
            tenant_id="tenant-denied",
            provider_mode="disabled",
            allowed=False,
        ),
    ]

    samples = _build_tenant_samples(records=records)

    assert len(samples) == 1
    assert samples[0].tenant_id == "tenant-sg-001"


def test_build_capability_samples_include_task_source_and_async_job_type() -> None:
    records = [
        _record(
            request_id="air-1",
            caller_app="lotus-manage",
            task_id="knowledge_answer.v1",
            tenant_id="tenant-sg-001",
            provider_mode="catalog_only",
            allowed=True,
            source_ids=["lotus-platform-rfcs"],
        )
    ]
    jobs = [_job(job_id="job-1", caller_app="lotus-manage", job_type="retrieval_indexing")]

    samples = _build_capability_samples(records=records, jobs=jobs)

    assert any(
        sample.capability_kind == ObservabilityCapabilityKind.TASK
        and sample.capability_id == "knowledge_answer.v1"
        for sample in samples
    )
    assert any(
        sample.capability_kind == ObservabilityCapabilityKind.RETRIEVAL_SOURCE
        and sample.capability_id == "lotus-platform-rfcs"
        for sample in samples
    )
    assert any(
        sample.capability_kind == ObservabilityCapabilityKind.ASYNC_JOB_TYPE
        and sample.capability_id == "retrieval_indexing"
        for sample in samples
    )
