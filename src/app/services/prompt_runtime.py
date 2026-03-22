from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from app.contracts.prompts import (
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptRuntimeSelectionDescriptor,
)
from app.services.prompt_store import get_prompt_repository

_FOUNDATION_SELECTION_REASON = (
    "Foundation-phase runtime selects the single active prompt definition "
    "registered for each task."
)


@dataclass(frozen=True)
class ResolvedRuntimePrompt:
    prompt: PromptDescriptor
    selection: PromptRuntimeSelectionDescriptor


@dataclass(frozen=True)
class PromptLifecycleCounts:
    active_prompt_count: int
    retired_prompt_count: int


def list_registered_prompts() -> list[PromptDescriptor]:
    return get_prompt_repository().list_prompts()


def summarize_prompt_lifecycle_counts() -> PromptLifecycleCounts:
    prompts = list_registered_prompts()
    return PromptLifecycleCounts(
        active_prompt_count=sum(
            1 for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
        ),
        retired_prompt_count=sum(
            1 for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.RETIRED
        ),
    )


def list_active_runtime_prompts() -> list[ResolvedRuntimePrompt]:
    return [
        resolve_runtime_prompt_or_raise(prompt.task_id)
        for prompt in list_registered_prompts()
        if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    ]


def resolve_runtime_prompt_or_raise(task_id: str) -> ResolvedRuntimePrompt:
    prompt = get_prompt_repository().get_prompt(task_id)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered prompt definition for task_id: {task_id}",
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
        ),
    )
