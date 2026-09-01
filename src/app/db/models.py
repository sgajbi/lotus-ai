from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditRecordModel(Base):
    __tablename__ = "audit_records"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    output_label: Mapped[str] = mapped_column(String(64), nullable=False)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_selection_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    provider_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    # First-class model identity (issue #175 S2b). Nullable: rows written before
    # these columns existed read through the legacy JSON reconstruction instead.
    provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    adapter_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_catalogue_entry_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model_revision_pinned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    routing_decision_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    prompt_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sampling_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    provider_config_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_card_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    safety_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    redaction_posture: Mapped[str] = mapped_column(String(64), nullable=False)
    enforced_safety_controls: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    safety_outcome_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    output_validation_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    validation_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    authorization_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    stubbed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    context_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    result_preview: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class AuditAccessEventModel(Base):
    __tablename__ = "audit_access_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    caller_trust_source: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    denial_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    returned_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class RetrievalSourceModel(Base):
    __tablename__ = "retrieval_sources"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    documents: Mapped[list["RetrievalDocumentModel"]] = relationship(back_populates="source")
    index_jobs: Mapped[list["RetrievalIndexJobModel"]] = relationship(back_populates="source")


class RetrievalDocumentModel(Base):
    __tablename__ = "retrieval_documents"

    document_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[str] = mapped_column(String(64), nullable=False)

    source: Mapped["RetrievalSourceModel"] = relationship(back_populates="documents")
    chunks: Mapped[list["RetrievalChunkModel"]] = relationship(back_populates="document")
    versions: Mapped[list["RetrievalDocumentVersionModel"]] = relationship(
        back_populates="document"
    )


class RetrievalChunkModel(Base):
    __tablename__ = "retrieval_chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_documents.document_id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped["RetrievalDocumentModel"] = relationship(back_populates="chunks")


class RetrievalIndexJobModel(Base):
    __tablename__ = "retrieval_index_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped["RetrievalSourceModel"] = relationship(back_populates="index_jobs")


class RetrievalDocumentVersionModel(Base):
    __tablename__ = "retrieval_document_versions"

    version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_documents.document_id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    refresh_action: Mapped[str] = mapped_column(String(32), nullable=False)
    lineage_parent_version_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped["RetrievalDocumentModel"] = relationship(back_populates="versions")


class RetrievalIngestionJobModel(Base):
    __tablename__ = "retrieval_ingestion_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("retrieval_sources.source_id"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("retrieval_documents.document_id"), nullable=True, index=True
    )
    target_version_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    requested_action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class PromptDefinitionModel(Base):
    __tablename__ = "prompt_definitions"

    task_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    management_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    output_contract_notes: Mapped[str] = mapped_column(Text, nullable=False)


class PromptDefinitionVersionModel(Base):
    __tablename__ = "prompt_definition_versions"

    task_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    prompt_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    management_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    output_contract_notes: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class PromptRolloutStateModel(Base):
    __tablename__ = "prompt_rollout_state"

    task_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    active_prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    previous_active_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rollout_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_mutation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class PromptRolloutEventModel(Base):
    __tablename__ = "prompt_rollout_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(256), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    prior_active_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resulting_active_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prior_candidate_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resulting_candidate_prompt_version: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    authorization_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class ProviderQuotaStateModel(Base):
    __tablename__ = "provider_quota_state"

    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class ProviderBudgetStateModel(Base):
    __tablename__ = "provider_budget_state"

    budget_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    current_spend_usd: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class ProviderDegradationStateModel(Base):
    __tablename__ = "provider_degradation_state"

    degradation_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    circuit_open_until: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timeout_failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rate_limited_failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_error_failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class ProviderOperationsEventModel(Base):
    __tablename__ = "provider_operations_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(256), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(256), nullable=False)
    affected_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    authorization_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class CallerPolicyModel(Base):
    __tablename__ = "caller_policies"

    caller_app: Mapped[str] = mapped_column(String(128), primary_key=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_task_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    allowed_retrieval_source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    allow_live_provider: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_async_control: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_prompt_control: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_provider_control: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_audit_read_all_tenants: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tenant_policy_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    restricted_tenant_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class ArtifactMetadataModel(Base):
    __tablename__ = "artifact_metadata"

    artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_object_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    retention_posture: Mapped[str] = mapped_column(String(32), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    lineage_parent_artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    superseded_by_artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class AsyncJobModel(Base):
    __tablename__ = "async_jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    submitted_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_summary: Mapped[str] = mapped_column(Text, nullable=False)
    execution_path: Mapped[str] = mapped_column(String(128), nullable=False)
    related_evaluation_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latest_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    attempts: Mapped[list["AsyncJobAttemptModel"]] = relationship(back_populates="job")
    leases: Mapped[list["AsyncWorkerLeaseModel"]] = relationship(back_populates="job")


class WorkflowPackAdmissionLeaseModel(Base):
    __tablename__ = "workflow_pack_admission_leases"

    queue_item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_pack_id: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lane: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    admitted_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    caller_app: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow_surface: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_refs_payload: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)


class WorkflowPackAdmissionGuardModel(Base):
    __tablename__ = "workflow_pack_admission_guards"

    policy_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class AsyncJobAttemptModel(Base):
    __tablename__ = "async_job_attempts"

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("async_jobs.job_id"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claimed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    heartbeat_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_message: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["AsyncJobModel"] = relationship(back_populates="attempts")


class AsyncWorkerLeaseModel(Base):
    __tablename__ = "async_worker_leases"

    lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("async_jobs.job_id"), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    claimed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    heartbeat_at: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_expires_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    job: Mapped["AsyncJobModel"] = relationship(back_populates="leases")


class AsyncControlEventModel(Base):
    __tablename__ = "async_control_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("async_jobs.job_id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(256), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    prior_status: Mapped[str] = mapped_column(String(64), nullable=False)
    resulting_status: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_attempt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    authorization_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    triggered_by: Mapped[str] = mapped_column(String(256), nullable=False)
    submitted_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    async_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    latest_message: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)

    attempts: Mapped[list["EvaluationRunAttemptModel"]] = relationship(back_populates="run")
    case_results: Mapped[list["EvaluationCaseResultModel"]] = relationship(back_populates="run")


class EvaluationRunAttemptModel(Base):
    __tablename__ = "evaluation_run_attempts"

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.run_id"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latest_message: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["EvaluationRunModel"] = relationship(back_populates="attempts")


class EvaluationCaseResultModel(Base):
    __tablename__ = "evaluation_case_results"

    case_result_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.run_id"), nullable=False, index=True
    )
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fixture_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    artifact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    provider_config_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    run: Mapped["EvaluationRunModel"] = relationship(back_populates="case_results")


class WorkflowPackRunModel(Base):
    __tablename__ = "workflow_pack_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    pack_family: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    registration_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workflow_surface: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow_authority_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    runtime_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    stubbed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    output_preview: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_descriptors: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    artifact_refs: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    supersedes_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    superseded_by_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recovery_action_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_queue_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    recovery_decision_event_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    recovery_attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_workflow_pack_run_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    recovery_requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recovery_evidence_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    evaluator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evaluator_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_risk_status: Mapped[str] = mapped_column(String(64), nullable=False)
    model_risk_approval_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_config_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    replay_nonce: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    execution_started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    events: Mapped[list["WorkflowPackRunEventModel"]] = relationship(back_populates="run")


class WorkflowPackExecutionIdempotencyModel(Base):
    __tablename__ = "workflow_pack_execution_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "caller_app",
            "tenant_scope",
            "idempotency_key",
            name="uq_workflow_pack_execution_idempotency_scope",
        ),
    )

    record_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_scope: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    owner_token: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    response_checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class WorkflowPackRunEventModel(Base):
    __tablename__ = "workflow_pack_run_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_pack_runs.run_id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    runtime_state: Mapped[str] = mapped_column(String(32), nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    run: Mapped["WorkflowPackRunModel"] = relationship(back_populates="events")


class ProviderRetentionConfirmationModel(Base):
    __tablename__ = "provider_retention_confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_confirmation_ref: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    envelope_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class WorkflowPackTaskFlowModel(Base):
    __tablename__ = "workflow_pack_task_flows"

    task_flow_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    workflow_pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    caller: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workflow_surface: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workflow_authority_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    flow_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    supportability_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_step_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    descriptor_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    checkpoints: Mapped[list["WorkflowPackTaskFlowCheckpointModel"]] = relationship(
        back_populates="task_flow"
    )


class WorkflowPackTaskFlowCheckpointModel(Base):
    __tablename__ = "workflow_pack_task_flow_checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_flow_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_pack_task_flows.task_flow_id"), nullable=False, index=True
    )
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transition: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    unsupported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    descriptor_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    task_flow: Mapped["WorkflowPackTaskFlowModel"] = relationship(back_populates="checkpoints")


class WorkflowPackQueueEventModel(Base):
    __tablename__ = "workflow_pack_queue_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    queue_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workflow_pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_pack_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lane: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    caller_app: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workflow_surface: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    descriptor_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class WorkflowPackRegistrationModel(Base):
    __tablename__ = "workflow_pack_registrations"

    pack_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    pack_family: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_repository: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_service: Mapped[str] = mapped_column(String(128), nullable=False)
    truth_owner_services: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    primary_use_case: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_authority_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    default_execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    definition_ref: Mapped[str] = mapped_column(Text, nullable=False)
    definition_refs: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    compatibility_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    registration_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    activation_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    registered_definition_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    supported_callers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    supported_identity_classes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    supported_environments: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tenant_scope: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    surface_scope: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    default_rollout_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    pause_state: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes: Mapped[str | None] = mapped_column(String(256), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    registered_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    registered_by: Mapped[str] = mapped_column(String(128), nullable=False)
    last_activated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_changed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status_summary: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class WorkflowPackControlEventModel(Base):
    __tablename__ = "workflow_pack_control_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    prior_registration_status: Mapped[str] = mapped_column(String(32), nullable=False)
    resulting_registration_status: Mapped[str] = mapped_column(String(32), nullable=False)
    prior_activation_state: Mapped[str] = mapped_column(String(32), nullable=False)
    resulting_activation_state: Mapped[str] = mapped_column(String(32), nullable=False)
    caller_app: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class RateCardModel(Base):
    __tablename__ = "rate_cards"

    card_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_target: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    input_cost_per_1k_tokens: Mapped[float] = mapped_column(Float, nullable=False)
    output_cost_per_1k_tokens: Mapped[float] = mapped_column(Float, nullable=False)
    effective_from_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_to_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    last_updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class KillSwitchActivationModel(Base):
    __tablename__ = "kill_switch_activations"

    switch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    semantics: Mapped[str] = mapped_column(
        String(16), nullable=False, default="HARD_KILL", server_default="HARD_KILL"
    )
    target: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    activated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_recorded_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cleared_at: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    cleared_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clear_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelCatalogueLifecycleEventModel(Base):
    __tablename__ = "model_catalogue_lifecycle_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_evidence_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class ModelRevisionDriftObservationModel(Base):
    __tablename__ = "model_revision_drift_observations"

    observation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    expected_identity: Mapped[str] = mapped_column(String(256), nullable=False)
    observed_model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    revision_pinned_at_observation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    first_observed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    last_observed_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)


class ModelCatalogueEntryModel(Base):
    __tablename__ = "model_catalogue_entries"

    entry_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    model_family: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    deployment: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    revision_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    modalities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    context_window_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_structured_output: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    supports_tool_calling: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    supports_streaming: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    approved_workflow_pack_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    approval_evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    approved_from_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_until_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed_source: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    last_updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
