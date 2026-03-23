from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.contracts.prompts import (
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptRolloutDescriptor,
    PromptRolloutRole,
    PromptRuntimeSelectionDescriptor,
)
from app.services.prompt_store import get_prompt_repository
from app.services.prompt_rollout_models import PromptRolloutStateRecord

_FOUNDATION_SELECTION_REASON = (
    "Runtime selection resolves through durable prompt rollout state and explicit governed prompt control actions."
)


@dataclass(frozen=True)
class ResolvedRuntimePrompt:
    prompt: PromptDescriptor
    selection: PromptRuntimeSelectionDescriptor


@dataclass(frozen=True)
class PromptLifecycleCounts:
    active_prompt_count: int
    retired_prompt_count: int
    candidate_prompt_count: int


def list_registered_prompts() -> list[PromptDescriptor]:
    return get_prompt_repository().list_prompt_versions()


def list_prompt_rollout_states() -> list[PromptRolloutStateRecord]:
    return get_prompt_repository().list_prompt_rollout_states()


def summarize_prompt_lifecycle_counts() -> PromptLifecycleCounts:
    prompts = list_registered_prompts()
    rollout_states = list_prompt_rollout_states()
    active_prompt_count = sum(
        1 for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    )
    retired_prompt_count = sum(
        1 for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.RETIRED
    )
    candidate_prompt_count = sum(
        1 for state in rollout_states if state.candidate_prompt_version is not None
    )
    return PromptLifecycleCounts(
        active_prompt_count=active_prompt_count,
        retired_prompt_count=retired_prompt_count,
        candidate_prompt_count=candidate_prompt_count,
    )


def list_active_runtime_prompts() -> list[ResolvedRuntimePrompt]:
    return [
        resolve_runtime_prompt_or_raise(rollout_state.task_id)
        for rollout_state in list_prompt_rollout_states()
    ]


def list_prompt_rollout_descriptors() -> list[PromptRolloutDescriptor]:
    return [
        PromptRolloutDescriptor(
            task_id=state.task_id,
            active_prompt_version=state.active_prompt_version,
            candidate_prompt_version=state.candidate_prompt_version,
            previous_active_prompt_version=state.previous_active_prompt_version,
            rollout_mode=state.rollout_mode,
            runtime_mutation_enabled=state.runtime_mutation_enabled,
            selection_reason=_FOUNDATION_SELECTION_REASON,
        )
        for state in list_prompt_rollout_states()
    ]


def resolve_runtime_prompt_or_raise(task_id: str) -> ResolvedRuntimePrompt:
    rollout_state = get_prompt_repository().get_prompt_rollout_state(task_id)
    if rollout_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed prompt rollout state for task_id: {task_id}",
        )
    prompt = get_prompt_repository().get_prompt_version(task_id, rollout_state.active_prompt_version)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Prompt rollout state references a missing active prompt version "
                f"for task_id: {task_id}"
            ),
        )
    if prompt.lifecycle_status != PromptLifecycleStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Prompt definition is not active for runtime selection: {task_id}",
        )
    return ResolvedRuntimePrompt(
        prompt=prompt,
        selection=PromptRuntimeSelectionDescriptor(
            task_id=prompt.task_id,
            prompt_version=prompt.prompt_version,
            lifecycle_status=prompt.lifecycle_status,
            management_mode=prompt.management_mode,
            source_reference=prompt.source_reference,
            selected_for_runtime=True,
            selection_reason=_FOUNDATION_SELECTION_REASON,
            rollout_role=PromptRolloutRole.ACTIVE,
        ),
    )
