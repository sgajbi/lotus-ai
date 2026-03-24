from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.evals import EvaluationApprovalGateSummaryDescriptor


class PromptLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANDIDATE = "CANDIDATE"
    RETIRED = "RETIRED"


class PromptManagementMode(str, Enum):
    SEEDED_MEMORY = "SEEDED_MEMORY"
    MIGRATION_MANAGED = "MIGRATION_MANAGED"


class PromptRolloutRole(str, Enum):
    ACTIVE = "ACTIVE"
    CANDIDATE = "CANDIDATE"
    PREVIOUS_ACTIVE = "PREVIOUS_ACTIVE"


class PromptRolloutSelectionMode(str, Enum):
    GOVERNED_STATE_READ_ONLY = "GOVERNED_STATE_READ_ONLY"
    GOVERNED_CONTROL_ACTIONS = "GOVERNED_CONTROL_ACTIONS"


class PromptDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier associated with the prompt.")
    prompt_version: str = Field(description="Version of the prompt definition.")
    prompt_kind: str = Field(description="High-level type of prompt definition.")
    lifecycle_status: PromptLifecycleStatus = Field(
        description="Lifecycle state for the prompt definition."
    )
    management_mode: PromptManagementMode = Field(
        description="How the prompt definition is currently managed."
    )
    source_reference: str = Field(
        description="Repository or migration reference showing where the prompt definition came from."
    )
    system_instructions: str = Field(description="Primary system instructions for the task.")
    output_contract_notes: str = Field(
        description="Contract notes constraining how task output should behave."
    )


class PromptGovernanceStatusResponse(BaseModel):
    prompt_store_mode: str = Field(description="Configured prompt store mode for the runtime.")
    management_mode: PromptManagementMode = Field(
        description="Effective prompt management mode for the current runtime."
    )
    runtime_mutation_enabled: bool = Field(
        description="Whether runtime prompt mutation APIs are enabled."
    )
    promotion_write_api_enabled: bool = Field(
        description="Whether prompt promotion is supported through a write API."
    )
    promotion_path: str = Field(
        description="Approved path for promoting prompt definitions in the current phase."
    )
    active_prompt_count: int = Field(description="Number of currently active prompt definitions.")
    control_history_endpoint: str = Field(
        description="Inspectable endpoint exposing durable prompt control-plane history."
    )


class PromptControlActionType(str, Enum):
    PROMOTE_CANDIDATE = "PROMOTE_CANDIDATE"
    ROLLBACK_TO_PREVIOUS_ACTIVE = "ROLLBACK_TO_PREVIOUS_ACTIVE"


class PromptControlEventDescriptor(BaseModel):
    event_id: str = Field(description="Stable identifier for the prompt control-plane event.")
    task_id: str = Field(description="Stable task identifier targeted by the action.")
    action_type: PromptControlActionType = Field(
        description="Governed control-plane action applied to the prompt rollout state."
    )
    requested_by: str = Field(description="Operator identity that requested the action.")
    approved_by: str = Field(description="Operator identity that approved the action.")
    reason: str = Field(description="Recorded operator reason for the action.")
    prior_active_prompt_version: str | None = Field(
        default=None,
        description="Active prompt version before the control action ran.",
    )
    resulting_active_prompt_version: str | None = Field(
        default=None,
        description="Active prompt version after the control action completed.",
    )
    prior_candidate_prompt_version: str | None = Field(
        default=None,
        description="Candidate prompt version before the control action ran, if any.",
    )
    resulting_candidate_prompt_version: str | None = Field(
        default=None,
        description="Candidate prompt version after the control action completed, if any.",
    )
    authorization: AuthorizationDecision = Field(
        description="Typed caller-authorization decision recorded for the prompt control action."
    )
    recorded_at: str = Field(description="UTC timestamp when the control action was recorded.")


class PromptControlActionRequest(BaseModel):
    task_id: str = Field(description="Stable task identifier targeted by the control action.")
    action_type: PromptControlActionType = Field(
        description="Governed prompt control-plane action to apply."
    )
    caller_app: str = Field(
        description="Caller application identity authorized to issue the prompt control action."
    )
    candidate_prompt_version: str | None = Field(
        default=None,
        description="Candidate prompt version to promote. Required for promotion and omitted for rollback.",
    )
    requested_by: str = Field(description="Operator identity requesting the action.")
    approved_by: str = Field(description="Operator identity approving the action.")
    reason: str = Field(description="Human-readable operator reason for the change.")


class PromptControlActionResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt control response.")
    version: str = Field(description="Current lotus-ai service version.")
    event: PromptControlEventDescriptor = Field(
        description="Durable prompt control-plane event that was recorded."
    )
    rollout_state: PromptRolloutDescriptor = Field(
        description="Resulting rollout state after the control action completed."
    )
    summary: list[str] = Field(
        description="Human-readable summary of the prompt control action outcome."
    )


class PromptControlHistoryResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt control history view.")
    version: str = Field(description="Current lotus-ai service version.")
    prompt_store_mode: str = Field(description="Configured prompt store mode for the runtime.")
    supported_action_types: list[PromptControlActionType] = Field(
        description="Governed prompt control-plane actions currently supported by the runtime."
    )
    latest_events: list[PromptControlEventDescriptor] = Field(
        description="Most recent durable prompt control-plane events."
    )
    notes: list[str] = Field(
        description="Operational notes explaining current prompt control-plane posture."
    )


class PromptSelectionMode(str, Enum):
    STATIC_ACTIVE = "STATIC_ACTIVE"
    ROLLOUT_STATE_ACTIVE = "ROLLOUT_STATE_ACTIVE"


class PromptRuntimeSelectionDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier associated with the prompt.")
    prompt_version: str = Field(description="Prompt version currently selected at runtime.")
    lifecycle_status: PromptLifecycleStatus = Field(
        description="Lifecycle status of the selected prompt definition."
    )
    management_mode: PromptManagementMode = Field(
        description="Management mode for the selected prompt definition."
    )
    source_reference: str = Field(
        description="Repository or migration reference for the selected prompt definition."
    )
    selected_for_runtime: bool = Field(
        description="Whether the prompt definition is currently selected for runtime use."
    )
    selection_reason: str = Field(
        description="Human-readable explanation of why this prompt is selected."
    )
    rollout_role: PromptRolloutRole = Field(
        description="Current rollout role associated with the prompt version."
    )


class PromptSelectionTraceDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier associated with the prompt selection.")
    prompt_version: str = Field(
        description="Prompt version selected for this execution or audit trace."
    )
    rollout_role: PromptRolloutRole = Field(
        description="Rollout role associated with the selected prompt version."
    )
    selection_reason: str = Field(
        description="Human-readable explanation of why this prompt version was selected."
    )
    active_prompt_version: str = Field(
        description="Currently active prompt version for the task at selection time."
    )
    candidate_prompt_version: str | None = Field(
        default=None,
        description="Candidate prompt version visible at selection time, if any.",
    )
    previous_active_prompt_version: str | None = Field(
        default=None,
        description="Prior active prompt version retained for rollback review at selection time, if any.",
    )
    latest_control_event: PromptControlEventDescriptor | None = Field(
        default=None,
        description="Most recent durable prompt control event known at selection time, if any.",
    )


class PromptRolloutDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier associated with the rollout state.")
    active_prompt_version: str = Field(
        description="Prompt version currently selected for runtime use."
    )
    candidate_prompt_version: str | None = Field(
        default=None,
        description="Prompt version staged as a candidate for future promotion, if any.",
    )
    previous_active_prompt_version: str | None = Field(
        default=None,
        description="Prior active prompt version retained for reviewable rollback, if any.",
    )
    rollout_mode: PromptRolloutSelectionMode = Field(
        description="How rollout state is currently governed for the task."
    )
    runtime_mutation_enabled: bool = Field(
        description="Whether runtime mutation is currently enabled for this task rollout state."
    )
    selection_reason: str = Field(
        description="Human-readable explanation of why the active prompt remains selected."
    )
    latest_control_event: PromptControlEventDescriptor | None = Field(
        default=None,
        description="Most recent durable prompt control event known for this rollout state, if any.",
    )


class PromptRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    prompt_store_mode: str = Field(description="Configured prompt store mode for the runtime.")
    selection_mode: PromptSelectionMode = Field(
        description="How prompt definitions are selected for runtime use."
    )
    rollout_mode: PromptRolloutSelectionMode = Field(
        description="How durable prompt rollout state is currently managed."
    )
    active_prompt_count: int = Field(description="Number of active prompt definitions.")
    retired_prompt_count: int = Field(description="Number of retired prompt definitions.")
    candidate_prompt_count: int = Field(description="Number of candidate prompt definitions.")
    selections: list[PromptRuntimeSelectionDescriptor] = Field(
        description="Prompt definitions currently selected for runtime use."
    )
    rollout_states: list[PromptRolloutDescriptor] = Field(
        description="Durable prompt rollout state visible to the current runtime."
    )


class PromptActivationReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt activation readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    prompt_store_mode: str = Field(description="Configured prompt store mode for the runtime.")
    management_mode: PromptManagementMode = Field(
        description="Effective prompt management mode for the current runtime."
    )
    activation_ready: bool = Field(
        description="Whether prompt rollout posture is currently ready for a live activation change."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why prompt rollout is not yet activatable through a live promotion path."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before live prompt promotion can be enabled."
    )


class PromptRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable prompt runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before live prompt rollout activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class PromptRunbookReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt runbook readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether prompt operational runbook readiness is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of prompt runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required prompt runbook items currently marked complete."
    )
    items: list[PromptRunbookReadinessItem] = Field(
        description="Governed prompt operational runbook readiness items."
    )


class PromptEvidenceReadinessItem(BaseModel):
    evidence_id: str = Field(description="Stable prompt evidence-readiness item identifier.")
    status: str = Field(description="Current readiness posture for the evidence requirement.")
    required_for_activation: bool = Field(
        description="Whether this evidence item must be complete before live prompt rollout activation."
    )
    notes: str = Field(description="Human-readable explanation of the evidence requirement.")


class PromptEvidenceReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt evidence readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    evidence_ready: bool = Field(
        description="Whether prompt evidence posture is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of prompt evidence items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required prompt evidence items currently marked complete."
    )
    items: list[PromptEvidenceReadinessItem] = Field(
        description="Governed prompt evidence-readiness items."
    )
    approval_gate: EvaluationApprovalGateSummaryDescriptor = Field(
        description="Runtime-backed approval evidence summary for the prompt rollout domain."
    )


class PromptGovernanceStatusSummaryResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt governance status view.")
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether prompt governance posture is currently sufficient for live activation."
    )
    activation_readiness: PromptActivationReadinessResponse = Field(
        description="Technical activation-readiness summary for prompt rollout."
    )
    runbook_readiness: PromptRunbookReadinessResponse = Field(
        description="Operational runbook-readiness summary for prompt rollout."
    )
    evidence_readiness: PromptEvidenceReadinessResponse = Field(
        description="Evaluation and audit evidence-readiness summary for prompt rollout."
    )
    blocking_area_count: int = Field(
        description="Number of top-level prompt governance areas currently blocking activation."
    )
    governance_summary: list[str] = Field(
        description="Human-readable summary of the current prompt governance posture."
    )
