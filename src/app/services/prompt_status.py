from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptLifecycleStatus,
    PromptRuntimeSelectionDescriptor,
    PromptRuntimeStatusResponse,
    PromptSelectionMode,
)
from app.services.prompt_registry import list_registered_prompts


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
        selections=[
            PromptRuntimeSelectionDescriptor(
                task_id=prompt.task_id,
                prompt_version=prompt.prompt_version,
                lifecycle_status=prompt.lifecycle_status,
                management_mode=prompt.management_mode,
                source_reference=prompt.source_reference,
                selected_for_runtime=True,
                selection_reason=(
                    "Foundation-phase runtime selects the single active prompt definition "
                    "registered for each task."
                ),
            )
            for prompt in active_prompts
        ],
    )
