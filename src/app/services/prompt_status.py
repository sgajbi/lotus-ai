from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptLifecycleStatus,
    PromptRuntimeStatusResponse,
    PromptSelectionMode,
)
from app.services.prompt_runtime import list_active_runtime_prompts, list_registered_prompts


def build_prompt_runtime_status() -> PromptRuntimeStatusResponse:
    prompts = list_registered_prompts()
    active_prompts = [
        prompt for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    ]
    retired_prompts = [
        prompt for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.RETIRED
    ]
    return PromptRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        prompt_store_mode=settings.prompt_store_mode,
        selection_mode=PromptSelectionMode.STATIC_ACTIVE,
        active_prompt_count=len(active_prompts),
        retired_prompt_count=len(retired_prompts),
        selections=[resolved.selection for resolved in list_active_runtime_prompts()],
    )
