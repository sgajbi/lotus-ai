from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PromptLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class PromptManagementMode(str, Enum):
    SEEDED_MEMORY = "SEEDED_MEMORY"
    MIGRATION_MANAGED = "MIGRATION_MANAGED"


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


class PromptSelectionMode(str, Enum):
    STATIC_ACTIVE = "STATIC_ACTIVE"


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


class PromptRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the prompt runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    prompt_store_mode: str = Field(description="Configured prompt store mode for the runtime.")
    selection_mode: PromptSelectionMode = Field(
        description="How prompt definitions are selected for runtime use."
    )
    active_prompt_count: int = Field(description="Number of active prompt definitions.")
    retired_prompt_count: int = Field(description="Number of retired prompt definitions.")
    selections: list[PromptRuntimeSelectionDescriptor] = Field(
        description="Prompt definitions currently selected for runtime use."
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
