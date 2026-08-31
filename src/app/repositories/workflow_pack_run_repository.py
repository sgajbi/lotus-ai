from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.evidence import ExecutionEvidenceDescriptor


@dataclass(frozen=True)
class WorkflowPackRunRecord:
    run_id: str
    pack_id: str
    pack_family: str
    pack_version: str
    registration_ref: str
    task_id: str
    request_id: str
    caller_app: str
    correlation_id: str
    tenant_id: str | None
    workflow_surface: str | None
    workflow_authority_owner: str
    runtime_state: str
    review_state: str
    review_required: bool
    provider_mode: str
    stubbed: bool
    output_preview: str
    structured_output_keys: list[str]
    evidence_descriptors: list[ExecutionEvidenceDescriptor]
    artifact_refs: list[ArtifactDescriptor]
    supersedes_run_id: str | None
    superseded_by_run_id: str | None
    created_at: str
    completed_at: str | None
    last_updated_at: str
    recovery_action_type: str | None = None
    source_queue_item_id: str | None = None
    recovery_decision_event_id: str | None = None
    recovery_attempt_number: int | None = None
    source_workflow_pack_run_id: str | None = None
    recovery_requested_by: str | None = None
    recovery_evidence_ref: str | None = None
    evaluator_id: str = "unverifiable"
    evaluator_policy_version: str = "unverifiable"
    provider_id: str = "unverifiable"
    model_id: str = "unverifiable"
    model_version: str = "unverifiable"
    model_risk_status: str = "unverifiable"
    model_risk_approval_ref: str = "unverifiable"
    provider_config_sha256: str | None = None
    input_evidence_sha256: str = "unverifiable"
    output_content_sha256: str = "unverifiable"
    replay_nonce: str = "unverifiable"
    execution_started_at: str = "unverifiable"


@dataclass(frozen=True)
class WorkflowPackRunEventRecord:
    event_id: str
    run_id: str
    event_type: str
    runtime_state: str
    review_state: str
    actor: str
    message: str
    recorded_at: str


class WorkflowPackRunRepository(Protocol):
    def list_runs(self, *, limit: int | None = None) -> list[WorkflowPackRunRecord]:
        """List persisted workflow-pack run records, optionally bounded to newest records."""

    def query_runs(
        self,
        *,
        registration_ref: str | None = None,
        pack_id: str | None = None,
        pack_family: str | None = None,
        caller_app: str | None = None,
        tenant_id: str | None = None,
        workflow_surface: str | None = None,
        runtime_state: str | None = None,
        review_state: str | None = None,
        workflow_authority_owner: str | None = None,
        limit: int,
    ) -> list[WorkflowPackRunRecord]:
        """List newest workflow-pack run records matching repository-owned filters."""

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        """Fetch one persisted workflow-pack run record."""

    def save_run(self, record: WorkflowPackRunRecord) -> None:
        """Persist one workflow-pack run record."""

    def list_events(self, *, run_id: str) -> list[WorkflowPackRunEventRecord]:
        """List persisted events for one workflow-pack run."""

    def save_event(self, record: WorkflowPackRunEventRecord) -> None:
        """Persist one workflow-pack run event."""
