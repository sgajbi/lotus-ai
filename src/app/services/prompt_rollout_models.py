from __future__ import annotations

from dataclasses import dataclass

from app.contracts.prompts import (
    PromptControlActionType,
    PromptDescriptor,
    PromptRolloutSelectionMode,
)


@dataclass(frozen=True)
class PromptRolloutStateRecord:
    task_id: str
    active_prompt_version: str
    candidate_prompt_version: str | None
    previous_active_prompt_version: str | None
    rollout_mode: PromptRolloutSelectionMode
    runtime_mutation_enabled: bool


@dataclass(frozen=True)
class PromptRolloutEventRecord:
    event_id: str
    task_id: str
    action_type: PromptControlActionType
    requested_by: str
    approved_by: str
    reason: str
    prior_active_prompt_version: str | None
    resulting_active_prompt_version: str | None
    prior_candidate_prompt_version: str | None
    resulting_candidate_prompt_version: str | None
    recorded_at: str


@dataclass(frozen=True)
class PromptRuntimeInventory:
    definitions: list[PromptDescriptor]
    rollout_states: list[PromptRolloutStateRecord]
