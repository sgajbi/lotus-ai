from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.output_validation import OutputValidationOutcome
from app.contracts.capability_requirements import CapabilityRequirements
from app.contracts.evidence import ExecutionEvidenceBundle
from app.contracts.prompts import PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderAdapterKind, RoutingDecisionDescriptor
from app.contracts.safety import SafetyExecutionOutcome


class TaskCategory(str, Enum):
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    GENERATE_STRUCTURED = "generate_structured"
    KNOWLEDGE_SEARCH = "knowledge_search"
    KNOWLEDGE_ANSWER = "knowledge_answer"


class OutputLabel(str, Enum):
    EXPLANATION_ONLY = "EXPLANATION_ONLY"
    DRAFT = "DRAFT"
    CLASSIFICATION = "CLASSIFICATION"
    RETRIEVAL_ANSWER = "RETRIEVAL_ANSWER"


class TaskInputMode(str, Enum):
    STRUCTURED_CONTEXT = "STRUCTURED_CONTEXT"


class TaskExecutionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class CapabilityDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier.")
    category: TaskCategory = Field(description="Task category owned by lotus-ai.")
    enabled: bool = Field(description="Whether the task is currently enabled.")
    output_label: OutputLabel = Field(description="Intended use label for the task output.")
    description: str = Field(description="Human-readable task description.")
    redaction_allowlisted_types: list[str] = Field(
        default_factory=list,
        description="Redaction detector classes this task's output contract legitimately "
        "carries (issue #150); an allowlisted class is skipped for this task only, never "
        "globally.",
    )


class CapabilityCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the catalog.")
    version: str = Field(description="Service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    tasks: list[CapabilityDescriptor] = Field(
        description="Bounded AI task capabilities currently exposed by the service."
    )


class CallerMetadata(BaseModel):
    caller_app: str = Field(description="Calling Lotus application or platform component.")
    correlation_id: str = Field(description="Correlation identifier propagated by the caller.")
    requested_by: str | None = Field(
        default=None,
        description="Optional human or system identity associated with the request.",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant or environment ownership marker for the request.",
    )


class TaskContextEnvelope(BaseModel):
    summary: str = Field(description="Short human-readable description of the provided context.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured task context assembled by the calling Lotus application.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Optional source references carried by the calling system.",
    )


class TaskExecutionRequest(BaseModel):
    task_id: str = Field(description="Stable Lotus AI task identifier.")
    input_mode: TaskInputMode = Field(description="How the task input context is provided.")
    caller: CallerMetadata = Field(description="Calling system metadata.")
    context: TaskContextEnvelope = Field(description="Structured context envelope for execution.")
    requirements: CapabilityRequirements | None = Field(
        default=None,
        description=(
            "Optional workload requirements (issue #244, S1). Validated and recorded as "
            "execution evidence with an explicit NOT_ENFORCED posture until capability "
            "eligibility ships; absent means today's routing behaviour, unchanged."
        ),
    )
    expected_output_label: OutputLabel | None = Field(
        default=None,
        description="Optional caller assertion about the expected output label for the task.",
    )


class TaskAuditMetadata(BaseModel):
    request_id: str = Field(description="Generated task execution request identifier.")
    output_validation: OutputValidationOutcome | None = Field(
        default=None,
        description=(
            "Deterministic output-validation verdict for this execution; null only when "
            "no provider output was produced (runtime failure before execution)."
        ),
    )
    workflow_pack_run_id: str | None = Field(
        default=None,
        description=(
            "Optional workflow-pack run identifier when the task execution is bound to an "
            "explicit or inferred workflow-pack execution path."
        ),
    )
    task_id: str = Field(description="Task identifier evaluated for this execution.")
    output_label: OutputLabel = Field(description="Output label attached to the execution.")
    prompt_version: str = Field(description="Prompt version associated with the execution.")
    prompt_selection: PromptSelectionTraceDescriptor = Field(
        description="Detailed prompt rollout selection trace associated with the execution."
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
        "provider request was built (knowledge/retrieval paths, failures before execution).",
    )
    provider_config_sha256: str | None = Field(
        default=None,
        description="Digest of the resolved execution configuration (model identity + "
        "sampling); reproducibility key for this execution.",
    )
    estimated_cost_usd: float | None = Field(
        default=None,
        description="Estimated execution cost in USD from the effective rate card "
        "(issue #178 S4); null is the explicit cost-unknown posture.",
    )
    rate_card_ref: str | None = Field(
        default=None,
        description="Identity of the rate card that priced this execution; null when no "
        "card was effective.",
    )
    safety: SafetyExecutionOutcome = Field(description="Safety posture resolved for the execution.")
    authorization: AuthorizationDecision = Field(
        description="Caller-authorization decision recorded for the execution."
    )
    generated_at: str = Field(description="UTC timestamp when the result was generated.")
    stubbed: bool = Field(description="Whether the result came from deterministic stub execution.")


class TaskExecutionResult(BaseModel):
    message: str = Field(description="Primary human-readable result string.")
    structured_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured result payload returned by the task execution layer.",
    )


class TaskExecutionResponse(BaseModel):
    status: TaskExecutionStatus = Field(description="Execution outcome for the task request.")
    output_validation: OutputValidationOutcome | None = Field(
        default=None,
        description=(
            "Deterministic output-validation verdict and authority marking for the "
            "returned result; null only when no provider output was produced."
        ),
    )
    task_id: str = Field(description="Executed task identifier.")
    category: TaskCategory = Field(description="Task category associated with the task id.")
    output_label: OutputLabel = Field(description="Output label emitted by the task.")
    result: TaskExecutionResult = Field(description="Task result payload.")
    audit: TaskAuditMetadata = Field(description="Audit metadata for the execution.")
    evidence: ExecutionEvidenceBundle = Field(
        description="Structured execution evidence explaining how the result was produced."
    )
