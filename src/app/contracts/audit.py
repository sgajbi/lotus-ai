from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.evidence import ExecutionEvidenceBundle
from app.contracts.prompts import PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderAdapterKind, RoutingDecisionDescriptor
from app.contracts.safety import RedactionPosture, SafetyExecutionOutcome
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus


class AuditTenantState(str, Enum):
    ATTRIBUTED = "ATTRIBUTED"
    LEGACY_UNATTRIBUTED = "LEGACY_UNATTRIBUTED"


class AuditRecordResponse(BaseModel):
    request_id: str = Field(description="Generated task execution request identifier.")
    execution_status: TaskExecutionStatus = Field(
        description="Execution outcome recorded for the task request."
    )
    task_id: str = Field(description="Task identifier evaluated for this execution.")
    category: TaskCategory = Field(description="Task category associated with the execution.")
    output_label: OutputLabel = Field(description="Output label emitted by the task execution.")
    caller_app: str = Field(description="Calling Lotus application associated with the request.")
    correlation_id: str = Field(description="Correlation identifier propagated by the caller.")
    requested_by: str | None = Field(
        default=None,
        description="Optional human or system identity associated with the request.",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant or environment ownership marker for the request.",
    )

    prompt_version: str = Field(description="Prompt version associated with the execution.")
    prompt_selection: PromptSelectionTraceDescriptor = Field(
        description="Detailed prompt rollout selection trace associated with the audit record."
    )
    provider_mode: str = Field(description="Provider mode active for the execution.")
    provider_id: str = Field(description="Resolved provider identifier used for the execution.")
    adapter_kind: ProviderAdapterKind | None = Field(
        default=None,
        description="Resolved provider adapter kind used for the execution when one is available.",
    )
    model_id: str | None = Field(
        default=None,
        description="Resolved provider model identifier used for the execution when one is available.",
    )
    model_version: str | None = Field(
        default=None,
        description="Governed model release or deployment version used for the execution.",
    )
    model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed model-catalogue entry the execution was bound to, on live paths.",
    )
    model_revision_pinned: bool | None = Field(
        default=None,
        description=(
            "Whether the bound catalogue entry pins an exact model revision "
            "(False means the family/tag fallback identity executed)."
        ),
    )
    routing_decision: RoutingDecisionDescriptor | None = Field(
        default=None,
        description="Recorded routing-policy decision that selected the provider path.",
    )
    prompt_content_sha256: str | None = Field(
        default=None,
        description="Canonical hash of the exact prompt content used (issue #151).",
    )
    sampling_parameters: dict[str, object] | None = Field(
        default=None,
        description="Explicit sampling configuration sent to the provider; null when no "
        "provider request was built.",
    )
    provider_config_sha256: str | None = Field(
        default=None,
        description="Digest of the resolved execution configuration (model identity + "
        "sampling); reproducibility key for this execution.",
    )
    safety_mode: str = Field(description="Safety mode applied to the execution.")
    redaction_posture: RedactionPosture = Field(
        description="Redaction posture associated with the executed task."
    )
    enforced_safety_controls: list[str] = Field(
        description="Stable identifiers for safety controls enforced for the execution."
    )
    safety_outcome: SafetyExecutionOutcome = Field(
        description="Typed safety execution outcome associated with the audit record."
    )
    authorization: AuthorizationDecision = Field(
        description="Caller-authorization decision recorded for the execution."
    )
    generated_at: str = Field(description="UTC timestamp when the record was created.")
    stubbed: bool = Field(description="Whether the execution result was stubbed.")
    context_summary: str = Field(description="Short summary of the caller-provided context.")
    context_keys: list[str] = Field(description="Sorted list of structured context keys.")
    source_refs: list[str] = Field(description="Source references carried by the caller.")
    result_preview: str = Field(description="Short preview of the generated result.")
    structured_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured task result stored in the audit record.",
    )
    evidence: ExecutionEvidenceBundle = Field(
        description="Structured execution evidence preserved with the audit record."
    )

    @computed_field(  # type: ignore[prop-decorator]
        description="Explicit tenant-attribution posture for audit inspection."
    )
    @property
    def tenant_state(self) -> AuditTenantState:
        return (
            AuditTenantState.ATTRIBUTED
            if self.tenant_id is not None
            else AuditTenantState.LEGACY_UNATTRIBUTED
        )


class AuditRecordCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the audit catalog response.")
    version: str = Field(description="Current lotus-ai service version.")
    record_count: int = Field(description="Number of audit records returned in this response.")
    filters_applied: dict[str, str | int] = Field(
        default_factory=dict,
        description="Bounded query filters applied while building the audit catalog response.",
    )
    records: list[AuditRecordResponse] = Field(
        description="Audit records matching the requested bounded filter set."
    )
