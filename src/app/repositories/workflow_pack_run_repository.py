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

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        """Fetch one persisted workflow-pack run record."""

    def save_run(self, record: WorkflowPackRunRecord) -> None:
        """Persist one workflow-pack run record."""

    def list_events(self, *, run_id: str) -> list[WorkflowPackRunEventRecord]:
        """List persisted events for one workflow-pack run."""

    def save_event(self, record: WorkflowPackRunEventRecord) -> None:
        """Persist one workflow-pack run event."""
