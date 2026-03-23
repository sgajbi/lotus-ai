from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptRolloutSelectionMode,
    PromptRuntimeStatusResponse,
    PromptSelectionMode,
)
from app.services.prompt_runtime import (
    list_active_runtime_prompts,
    list_prompt_rollout_descriptors,
    summarize_prompt_lifecycle_counts,
)


def build_prompt_runtime_status() -> PromptRuntimeStatusResponse:
    lifecycle_counts = summarize_prompt_lifecycle_counts()
    return PromptRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        prompt_store_mode=settings.prompt_store_mode,
        selection_mode=PromptSelectionMode.STATIC_ACTIVE,
        rollout_mode=PromptRolloutSelectionMode.GOVERNED_STATE_READ_ONLY,
        active_prompt_count=lifecycle_counts.active_prompt_count,
        retired_prompt_count=lifecycle_counts.retired_prompt_count,
        candidate_prompt_count=lifecycle_counts.candidate_prompt_count,
        selections=[resolved.selection for resolved in list_active_runtime_prompts()],
        rollout_states=list_prompt_rollout_descriptors(),
    )
